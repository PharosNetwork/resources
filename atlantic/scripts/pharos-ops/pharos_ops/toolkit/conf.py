#!/usr/bin/env python3
# coding=utf-8
"""
    Copyright (C) 2020 Pharos Labs. All rights reserved.

    Desc     : Pharos2.0 Operation Tools
    History  :
    License  : Pharos Labs proprietary/confidential.

    Python Version : 3.6.8
    Created by yuhuaxin.yhx
    Date: 2023/02/07
"""
import json
import string
import hashlib # for proposer id
import time
import re
from eth_utils import keccak, to_int, hexstr_if_str, to_bytes, int_to_big_endian

from collections import defaultdict
from typing import Dict
from os.path import join, abspath, isabs, dirname, samefile, exists

from pharos_ops.toolkit.schemas.deploy import *
from pharos_ops.toolkit.schemas.domain import *
from pharos_ops.toolkit import const, logs, utils, pharos
from pharos_ops.toolkit.conn_group import local

from pharos_ops.toolkit.utils import to_serializable
from .schemas import DomainSchema

def read_keyfile_to_hex(type: str, prikey_path: str, key_passwd: str):
    ret = local.run(f"openssl {type} -in {prikey_path} -noout -text -passin pass:{key_passwd}")
    if ret.ok:
        pass
    else:
        logs.error(ret.stderr)
        raise RuntimeError(f'Failed to execute openssl command: {ret.stderr}')
    
    output_lines = ret.stdout.splitlines()
    output_lines = [line for line in output_lines if re.match(r'^\s', line)]
    if len(output_lines) >= 4:
        output_lines = output_lines[3:]
    else:
        raise RuntimeError(f'Invalid openssl return: {output_lines}')
    
    out = ''.join(output_lines).replace(' ', '')
    out = ''.join(out.split(':'))
    
    return out


class Generator(object):
    """class for generate domain files of a chain"""

    def __init__(self, deploy_file: str, key_passwd: str = ""):
        self._deploy_file_path = dirname(abspath(deploy_file))
        deploy_data = utils.load_json(deploy_file)
        if key_passwd != "":
            deploy_data["domains"]["domain"]["key_passwd"] = key_passwd
            with open(deploy_file, "w") as fh:
                self._deploy = DeploySchema().load(deploy_data)
                json.dump(DeploySchema().dump(self._deploy), fh, indent=2)
        self._deploy = DeploySchema().load(deploy_data)
        if not samefile(self._abspath(self._deploy.build_root), dirname(self._deploy_file_path)):
            raise Exception('deploy file should be in $build_root/scripts')
        self._deploy.genesis_tpl = self._abspath(self._deploy.genesis_tpl)
        self._genesis_file = f'../conf/genesis.{self._deploy.chain_id}.conf'
        self._deploy.mygrid = deploy_data["mygrid"]
        self._domain_endpoints = {}
        self._is_light = False

    def _build_file(self, *args) -> str:
        return join(self._deploy.build_root, *args)

    def _abspath(self, file) -> str:
        return file if isabs(file) else join(self._deploy_file_path, file)

    def _start_port(self, start: int, service: str) -> int:
        # 自动获取peer(即rpc)端口
        if service == const.SERVICE_LIGHT:
            return start
        else:
            return start + const.SERVICES.index(service) * 1000

    def _generate_prikey(self, key_type:str, key_dir: str, key_file: str, key_passwd: str = "123abc"):
        prikey_path = join(key_dir, key_file)
        pubkey_file = key_file.replace('.key', '.pub')

        if exists(prikey_path):
            logs.debug(f"exsited key: {prikey_path}, override it with new key")
        else:
            logs.info(
                f'generate new key {prikey_path}')
            local.run(f'mkdir -p {key_dir}')

        if key_type not in [key_type.value for key_type in pharos.KeyType]:
            logs.error(f'{key_type} is not supported, please select from {[key_type.value for key_type in pharos.KeyType]}')
            return


        if key_type == pharos.KeyType.PRIME256V1.value:
            local.run(f"openssl ecparam -name prime256v1 -genkey | openssl pkcs8 -topk8 -outform pem -out {prikey_path} -v2 aes-256-cbc -v2prf hmacWithSHA256 -passout pass:{key_passwd}")
            pubkey, _ = Generator._get_pubkey(key_type, prikey_path, key_passwd)
            local.run(f"echo {pubkey} > {key_dir}/{pubkey_file}")

        elif key_type == pharos.KeyType.RSA.value:
            local.run(f"openssl genrsa 2048 | openssl pkcs8 -topk8 -outform pem -out {prikey_path} -v2 aes-256-cbc -v2prf hmacWithSHA256 -passout pass:{key_passwd}")
            pubkey, _ = Generator._get_pubkey(key_type, prikey_path, key_passwd)
            local.run(f"echo {pubkey} > {key_dir}/{pubkey_file}")

        elif key_type == pharos.KeyType.SM2.value:
            logs.error(f'{key_type} is not supported')

        elif key_type == pharos.KeyType.BLS12381.value:
            # OpenSSL does not support BLS key generation, so we use `pharos_cli` here
            # no passwd
            pharos_cli_path = self._build_file('bin', const.PHAROS_CLI)
            evmone_so_path = self._build_file('bin', const.EVMONE_SO)

            # The output is two line:
            # "PRIVKEY:0x4002xxxxxxxx"
            # "PUBKEY:0x4003xxxxxxxx"
            ret = local.run(f"LD_PRELOAD={evmone_so_path} {pharos_cli_path} crypto -t gen-key -a bls12381 | tail -n 2") # last 2-lines are prikey and pubkey
            # the `ret.stdout` will be `PRIVKEY:0x4002xxxxxxxx\nPUBKEY:0x4003xxxxxxxx`
            # so we split, then get contents
            bls_prikey = ret.stdout.split()[0].split(':')[1] # get prikey content
            bls_pubkey = ret.stdout.split()[1].split(':')[1] # get pubkey content

            local.run(f"echo {bls_prikey} > {key_dir}/{key_file}")
            local.run(f"echo {bls_pubkey} > {key_dir}/{pubkey_file}")


    def _get_pubkey(key_type:str, prikey_path: str, key_passwd: str = "123abc") -> (str, str):
        # pubkey prefix can refer to document: https://yuque.antfin-inc.com/pharoschain/pharos-node/tfcxty
 
        if not exists(prikey_path):
            logs.error(f"{prikey_path} does not exist")
            return

        if key_type not in [key_type.value for key_type in pharos.KeyType]:
            logs.error(f'{key_type} is not supported, please select from {[key_type.value for key_type in pharos.KeyType]}')
            return

        if key_type == pharos.KeyType.PRIME256V1.value:

            pubkey = '1003' + read_keyfile_to_hex('ec', prikey_path, key_passwd) # p256v1 prefix
            pubkey_bytes = bytes.fromhex(f'{pubkey}')
            return pubkey, pubkey_bytes

        elif key_type == pharos.keyType.RSA.value:
            pubkey = '1023' + read_keyfile_to_hex('rsa', prikey_path, key_passwd)  # rsa prefix
            pubkey_bytes = bytes.fromhex(f'{pubkey}')
            return pubkey, pubkey_bytes

        elif key_type == pharos.KeyType.SM2.value:
            logs.error(f'{key_type} is not supported')
            return ''

        elif key_type == pharos.KeyType.BLS12381.value:
            pass
        
        return ''

    def _string_to_hex_slots(self, s: str):
        # 将字符串转换为十六进制表示
        hex_string = s.encode('utf-8').hex()

        # 按 32 字节（64 个十六进制字符）分割
        slots = []
        for i in range(0, len(hex_string), 64):
            slot = hex_string[i:i+64]
            # 如果最后一个 slot 不足 64 个字符，用 0 填充
            slot = slot.ljust(64, '0')
            slots.append(slot)

        return slots
    
    def _short_string_to_slot(self, s: str):
        s_length = len(s.encode('utf-8')) * 2 # short string
        s_length_bytes = to_bytes(s_length).rjust(32, b'\0')
        hex_slots = bytes.fromhex(self._string_to_hex_slots(s)[0])
        final_bytes = self._bytes_bitwise_add(hex_slots, s_length_bytes)
        return final_bytes

    def _generate_string_slot(self, s:str, base_slot: bytes, string_slot: Dict[str, str]):
        s_length = len(s.encode('utf-8'))
        if (s_length <= 31): # short string, value and length are encoded together
            s_slot_bytes = self._short_string_to_slot(s)
            string_slot["0x" + base_slot.hex()] = "0x" + s_slot_bytes.hex()
        else: # long string
            # put length
            s_slot_length = s_length * 2 + 1 # larger than long bytes
            s_slot_length_bytes = to_bytes(s_slot_length).rjust(32, b'\0')
            string_slot["0x" + base_slot.hex()] = "0x" + s_slot_length_bytes.hex()
            # put values
            string_final_base_slot = keccak(base_slot)
            hex_slots = self._string_to_hex_slots(s)
            for i, slot in enumerate(hex_slots):
                slot_key = self._bytes_add_num(string_final_base_slot, i)
                string_slot["0x" + slot_key.hex()] = "0x" + slot


    def _bytes_add_num(self, a: bytes, b: int):
        a_num = int.from_bytes(a, 'big')
        result_num = a_num + b
        return result_num.to_bytes(32,'big')
    
    def _bytes_bitwise_add(self, bytes1: bytes, bytes2: bytes):
        if len(bytes1) != len(bytes2):
            raise ValueError("Both byte arrays must have the same length.")

        result = bytes(a | b for a, b in zip(bytes1, bytes2))
        return result



    def _generate_domain_slots(self, total_domains: int, domain_index: int, public_key: str, bls_pubkey: str, endpoint: str, stake: int):
        slots = {}

        # pool id
        if public_key.startswith('0x'):
            public_key = public_key[2:]  # Remove the '0x' prefix

        if bls_pubkey.startswith('0x'):
            bls_pubkey = bls_pubkey[2:]  # Remove the '0x' prefix

        
        # Compute the sha256 hash
        # public_key_bytes = public_key.encode('utf-8')
        # poolid = keccak(public_key_bytes)
        pubkey_bytes = bytes.fromhex(f'{public_key}')
        poolid = hashlib.sha256(bytes(pubkey_bytes)).digest()

        # 1. for `mapping(bytes32 => Validator) public validators`
        validators_map_base_slot = 0
        validators_map_base_slot_bytes = int_to_big_endian(validators_map_base_slot).rjust(32, b'\0')
        validators_map_validator_slot = keccak(poolid + validators_map_base_slot_bytes)

        # 2. for `Validator.description`
        validator_description_base_slot = 0
        validator_description_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_description_base_slot)
        description = "domain" + str(domain_index)
        description_length = len(description.encode('utf-8')) * 2 # short string
        description_length_bytes = to_bytes(description_length).rjust(32, b'\0')
        hex_slots = bytes.fromhex(self._string_to_hex_slots(description)[0])
        final_bytes = self._bytes_bitwise_add(hex_slots, description_length_bytes)
        slots["0x" + validator_description_map_base_slot.hex()] = "0x" + final_bytes.hex()

        # 3. for `Validator.publicKey`
        validator_public_key_base_slot = 1
        validator_public_key_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_public_key_base_slot)
        # 3.1 set string length
        public_key_length = len(public_key.encode('utf-8')) * 2 + 1 # larger than long bytes
        public_key_length_bytes = to_bytes(public_key_length).rjust(32, b'\0')
        slots["0x" + validator_public_key_map_base_slot.hex()] = "0x" + public_key_length_bytes.hex()
        # 3.2 set string
        public_key_final_base_slot = keccak(validator_public_key_map_base_slot)
        hex_slots = self._string_to_hex_slots(public_key)
        for i, slot in enumerate(hex_slots):
            public_key_slot = self._bytes_add_num(public_key_final_base_slot, i)
            slots["0x" + public_key_slot.hex()] = "0x" + slot

        # 4. for `Validator.blsPublicKey`
        validator_bls_public_key_base_slot = 3
        validator_bls_public_key_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_bls_public_key_base_slot)
        # 4.1 set string length
        bls_public_key_length = len(bls_pubkey.encode('utf-8')) * 2 + 1 # larger than long bytes
        bls_public_key_length_bytes = to_bytes(bls_public_key_length).rjust(32, b'\0')
        slots["0x" + validator_bls_public_key_map_base_slot.hex()] = "0x" + bls_public_key_length_bytes.hex()
        # 4.2 set string
        bls_public_key_final_base_slot = keccak(validator_bls_public_key_map_base_slot)
        bls_hex_slots = self._string_to_hex_slots(bls_pubkey)
        for i, slot in enumerate(bls_hex_slots):
            bls_public_key_slot = self._bytes_add_num(bls_public_key_final_base_slot, i)
            slots["0x" + bls_public_key_slot.hex()] = "0x" + slot

        # 5. for `Validator.endpoint`
        validator_endpoint_base_slot = 5
        validator_endpoint_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_endpoint_base_slot)
        endpoint_bytes = endpoint.encode('utf-8')
        endpoint_bytes_len = len(endpoint_bytes)

        if endpoint_bytes_len <= 31:  # Corrected condition
            # Less than or equal to 31 bytes: store directly
            endpoint_slot_value = bytearray(32)
            endpoint_slot_value[:endpoint_bytes_len] = endpoint_bytes
            endpoint_slot_value[31] = endpoint_bytes_len * 2 # Store length in the last byte
            slots["0x" + validator_endpoint_map_base_slot.hex()] = "0x" + endpoint_slot_value.hex()
        else:
            # 1. Store length (using the same encoding as publicKey)
            endpoint_bytes_len_encoded = endpoint_bytes_len * 2 + 1
            slots["0x" + validator_endpoint_map_base_slot.hex()] = "0x" + endpoint_bytes_len_encoded.to_bytes(32, 'big').hex()

            # 2. Calculate data location (using keccak on the base slot directly)
            data_location = int(keccak(validator_endpoint_map_base_slot).hex(), 16)

            for i in range(0, endpoint_bytes_len, 32):
                chunk = endpoint_bytes[i:i+32]
                slot_key = data_location + i // 32
                slots["0x" + slot_key.to_bytes(32, 'big').hex()] = "0x" + chunk.ljust(32, b'\0').hex()

        # 6. for `Validator.status`
        validator_status_slot = 6
        validator_status_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_status_slot)
        status = 1
        status_bytes = int_to_big_endian(status).rjust(32, b'\0')
        slots["0x" + validator_status_map_base_slot.hex()] = "0x" + status_bytes.hex()

        # 7. for `Validator.poolId`
        validator_pool_id_base_slot = 7
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_pool_id_base_slot)
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + poolid.hex()

        # 8. for `Validator.totalStake`
        validator_stake_base_slot = 8
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_stake_base_slot)
        stake_bytes = int_to_big_endian(stake).rjust(32, b'\0')
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + stake_bytes.hex()

        #9. for `validator.owner`
        validator_owner_base_slot = 9
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_owner_base_slot)
        root_sys_addr = self._deploy.admin_addr
        if root_sys_addr.startswith('0x'):
            root_sys_addr = root_sys_addr[2:]  # Remove the '0x' prefix
        root_sys_addr_slot_value = root_sys_addr.rjust(64, '0')
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + root_sys_addr_slot_value


        #10. for `validator.stakeSnapshot`
        validator_owner_base_slot = 10
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_owner_base_slot)
        stake_bytes = int_to_big_endian(stake).rjust(32, b'\0')
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + stake_bytes.hex()

        #11. for `validator.pendingWithdrawStake`
        validator_owner_base_slot = 11
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_owner_base_slot)
        pending_withdraw_stake = int_to_big_endian(0).rjust(32, b'\0')
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + pending_withdraw_stake.hex()

        #12. for `validator.pendingWithdrawWindow`
        validator_owner_base_slot = 12
        validator_pool_id_map_base_slot = self._bytes_add_num(validators_map_validator_slot, validator_owner_base_slot)
        pending_withdraw_window = int_to_big_endian(0).rjust(32, b'\0')
        slots["0x" + validator_pool_id_map_base_slot.hex()] = "0x" + pending_withdraw_window.hex()


        # 13. add for `bytes32[] public activePoolIds;`
        active_pool_ids_base_slot = 1
        ## 13.1 put array length
        active_pool_ids_base_slot_bytes = to_bytes(active_pool_ids_base_slot).rjust(32, b'\0')
        active_pool_ids_length = to_bytes(total_domains).rjust(32, b'\0')
        slots["0x" + active_pool_ids_base_slot_bytes.hex()] = "0x" + active_pool_ids_length.hex()
        ## 13.2 put array value
        active_pool_id_final_slot = keccak(active_pool_ids_base_slot_bytes)
        active_pool_id_final_validator_slot = self._bytes_add_num(active_pool_id_final_slot, domain_index)
        slots["0x" + active_pool_id_final_validator_slot.hex()] = "0x" + poolid.hex()

        # 15. config addr
        cfg_base_slot = 7
        cfg_base_slot_bytes = to_bytes(cfg_base_slot).rjust(32, b'\0')
        cfg_addr = "3100000000000000000000000000000000000000"
        cfg_addr_bytes = bytes.fromhex(cfg_addr).rjust(32, b'\0')
        slots["0x" + cfg_base_slot_bytes.hex()] = "0x" + cfg_addr_bytes.hex()

        return slots

    def _generate_chaincfg_slots(self, configs: Dict[str, str]):
        slots = {}

        config_cps_base_slot = 1
        config_cps_base_slot_bytes = int_to_big_endian(config_cps_base_slot).rjust(32, b'\0')

        # 1. put `configCps` length in `config_cps_base_slot`
        config_cps_length = 1 # put the genesis configs
        config_cps_length_bytes = int_to_big_endian(config_cps_length).rjust(32, b'\0')
        slots["0x" + config_cps_base_slot_bytes.hex()] = "0x" + config_cps_length_bytes.hex()

        # 2. put genesis `ConfigCheckpoint` into configCps
        genesis_config_cp_base_slot = keccak(config_cps_base_slot_bytes)

        # 3. put `ConfigCheckpoint.blockNum` and `ConfigCheckpoint.effectiveBlockNum`
        #    Two both are uint64, so they share the same slot
        block_nums = 0
        block_nums_bytes = int_to_big_endian(block_nums).rjust(32, b'\0')
        slots["0x" + genesis_config_cp_base_slot.hex()] = "0x" + block_nums_bytes.hex()

        # 4. put `Config[] configs`
        # 4.1 put `Config[] configs` length
        configs_base_slot = 1
        configs_base_slot_bytes = self._bytes_add_num(genesis_config_cp_base_slot, configs_base_slot)
        config_nums = len(configs)
        config_nums_bytes = int_to_big_endian(config_nums).rjust(32, b'\0')
        slots["0x" + configs_base_slot_bytes.hex()] = "0x" + config_nums_bytes.hex()

        # 4.2 put real genesis configs
        config_kvs_base_slot = keccak(configs_base_slot_bytes)
        slot_index = 0
        for config_key, config_value in configs.items():
            # key
            config_key_slot = self._bytes_add_num(config_kvs_base_slot, slot_index)
            self._generate_string_slot(config_key, config_key_slot, slots)
            slot_index += 1

            # value
            config_value_slot = self._bytes_add_num(config_kvs_base_slot, slot_index)
            self._generate_string_slot(config_value, config_value_slot, slots)
            slot_index += 1

        
        # 5. put stakingAddress
        config_root_sys_base_slot = 0
        config_root_sys_base_slot_bytes = int_to_big_endian(config_root_sys_base_slot).rjust(32, b'\0')
        sys_staking_addr = '4100000000000000000000000000000000000000'
        sys_staking_addr_bytes = bytes.fromhex(sys_staking_addr).rjust(32, b'\0')
        slots["0x" + config_root_sys_base_slot_bytes.hex()] = "0x" + sys_staking_addr_bytes.hex()

        return slots

    def _generate_rule_mng_slots(self, configs: Dict[str, str]):
        # administrator_
        root_sys_base_slot = 5
        root_sys_base_slot_bytes = int_to_big_endian(root_sys_base_slot).rjust(32, b'\0')
        admin_slot_hexkey = "0x" + root_sys_base_slot_bytes.hex()
        admin_slot_value = configs[admin_slot_hexkey]

        root_sys_addr = self._deploy.admin_addr
        if root_sys_addr.startswith('0x'):
            root_sys_addr = root_sys_addr[2:]  # Remove the '0x' prefix

        admin_slot_value = admin_slot_value[:-len(root_sys_addr)] + root_sys_addr

        configs["0x" + root_sys_base_slot_bytes.hex()] = admin_slot_value

        return configs

    def _generate_access_control_admin(self, configs: Dict[str, str], account: Optional[str]):
        """
        struct RoleData {
        mapping(address account => bool) hasRole;
        bytes32 adminRole;
        }

        bytes32 public constant DEFAULT_ADMIN_ROLE = 0x00;


        /// @custom:storage-location erc7201:openzeppelin.storage.AccessControl
        struct AccessControlStorage {
            mapping(bytes32 role => RoleData) _roles;
        }

        // keccak256(abi.encode(uint256(keccak256("openzeppelin.storage.AccessControl")) - 1)) & ~bytes32(uint256(0xff))
        bytes32 private constant AccessControlStorageLocation = 0x02dd7bc7dec4dceedda775e58dd541e08a116c6c53815c0bd028192f7b626800;

        function _getAccessControlStorage() private pure returns (AccessControlStorage storage $) {
            assembly {
                .slot := AccessControlStorageLocation
            }
        }

        function _grantRole(bytes32 role, address account) internal virtual returns (bool) {
            AccessControlStorage storage $ = _getAccessControlStorage();
            if (!hasRole(role, account)) {
                $._roles[role].hasRole[account] = true;
                emit RoleGranted(role, account, _msgSender());
                return true;
            } else {
                return false;
            }
        }
        """

        # either use admin_addr defined in `deploy.light.json`, or use the params
        if account is None:
            admin_addr = self._deploy.admin_addr
        else:
            admin_addr = account

        if admin_addr.startswith('0x'):
            admin_addr = admin_addr[2:]  # Remove the '0x' prefix


        access_control_storage_base_slot = "02dd7bc7dec4dceedda775e58dd541e08a116c6c53815c0bd028192f7b626800"
        access_control_storage_base_slot_bytes = bytes.fromhex(access_control_storage_base_slot).rjust(32, b'\0')
        default_admin_role_index = 0
        default_admin_role_index_bytes = int_to_big_endian(default_admin_role_index).rjust(32, b'\0')
        # now we have `RoleData` slot, i.e. `hasRole` field
        access_control_storage_default_admin_role_data_slot = keccak(default_admin_role_index_bytes + access_control_storage_base_slot_bytes)

        # get the account slot in `RoleData.hasRole` 
        admin_addr_bytes = bytes.fromhex(admin_addr).rjust(32, b'\0')
        admin_addr_slot = keccak(admin_addr_bytes + access_control_storage_default_admin_role_data_slot)
        # set the account role to true
        admin_addr_slot_value = 0x1
        admin_addr_slot_value_bytes = int_to_big_endian(admin_addr_slot_value).rjust(32, b'\0')

        # add to configs 
        configs["0x" + admin_addr_slot.hex()] = "0x" + admin_addr_slot_value_bytes.hex()

        # set the `adminRole` to `DEFAULT_ADMIN_ROLE` in `RoleData`
        if account is None: # we set system admin addr as `adminRole`
            admin_role_base_slot = 1
            admin_role_slot = self._bytes_add_num(access_control_storage_default_admin_role_data_slot, admin_role_base_slot)
            default_admin_role = 0x00
            admin_role_slot_value = int_to_big_endian(default_admin_role).rjust(32, b'\0')
            configs["0x" + admin_role_slot.hex()] = "0x" + admin_role_slot_value.hex()



    def _generate_disable_upgradeable_contract_initializers(self, configs: Dict[str, str]):
        """
        struct InitializableStorage {
            /**
             * @dev Indicates that the contract has been initialized.
             */
            uint64 _initialized;
            /**
             * @dev Indicates that the contract is in the process of being initialized.
             */
            bool _initializing;
        }

        // keccak256(abi.encode(uint256(keccak256("openzeppelin.storage.Initializable")) - 1)) & ~bytes32(uint256(0xff))
        bytes32 private constant INITIALIZABLE_STORAGE = 0xf0c57e16840df040f15088dc2f81fe391c3923bec73e23a9662efc9c229c6a00;

        function _disableInitializers() internal virtual {
            // solhint-disable-next-line var-name-mixedcase
            InitializableStorage storage $ = _getInitializableStorage();

            if ($._initializing) {
                revert InvalidInitialization();
            }
            if ($._initialized != type(uint64).max) {
                $._initialized = type(uint64).max;
                emit Initialized(type(uint64).max);
            }
        }
        function _getInitializableStorage() private pure returns (InitializableStorage storage $) {
            bytes32 slot = _initializableStorageSlot();
            assembly {
                $.slot := slot
            }
        }

        function _initializableStorageSlot() internal pure virtual returns (bytes32) {
            return INITIALIZABLE_STORAGE;
        }
        
        """

        initializable_storage_base_slot = "f0c57e16840df040f15088dc2f81fe391c3923bec73e23a9662efc9c229c6a00"
        initializable_storage_base_slot_bytes = bytes.fromhex(initializable_storage_base_slot).rjust(32, b'\0')

        # the `_initialized` and `_initializing` are in the same slot, so we set the value directly here
        # set `_initialized`
        initializable_storage_base_slot_value_of_initialized = 0xffffffffffffffff # uint64_max
        initialized_value_bytes_len = len(int_to_big_endian(initializable_storage_base_slot_value_of_initialized))
        initializable_storage_base_slot_value_of_initialized_bytes = int_to_big_endian(initializable_storage_base_slot_value_of_initialized).rjust(32, b'\0')

        # set `_initializing`
        initializable_storage_base_slot_value_of_initializing = 0x0 # false
        # left pad
        left_pad_length = 32 - initialized_value_bytes_len
        initializable_storage_base_slot_value_of_initializing_bytes = int_to_big_endian(initializable_storage_base_slot_value_of_initializing).rjust(left_pad_length, b'\0')
        # right pad. Actually when `_initializing` is false, the value is all-zeros
        initializable_storage_base_slot_value_of_initializing_bytes = initializable_storage_base_slot_value_of_initializing_bytes.ljust(32, b'\0')
        
        # bitwise merge `_initialized` and `_initializing`
        initializable_storage_base_slot_value = self._bytes_bitwise_add(initializable_storage_base_slot_value_of_initialized_bytes, initializable_storage_base_slot_value_of_initializing_bytes)

        configs["0x" + initializable_storage_base_slot_bytes.hex()] = "0x" + initializable_storage_base_slot_value.hex()

    def _generate_domain(self, domain_label: str, dinfo: DomainSummary) -> Domain:
        domain = Domain()
        # 所有domain公用的deploy字段
        domain.build_root = self._deploy.build_root
        domain.chain_id = self._deploy.chain_id
        domain.domain_label = domain_label
        domain.version = self._deploy.version
        domain.run_user = self._deploy.run_user
        domain.docker = self._deploy.docker
        domain.common.log = self._deploy.common.log
        domain.common.config = self._deploy.common.config
        domain.common.gflags = self._deploy.common.gflags
        domain.mygrid = self._deploy.mygrid
        domain.chain_protocol = self._deploy.chain_protocol

        logs.info(f'sys admin_addr is {self._deploy.admin_addr}')

        if self._deploy.use_generated_keys:
            default_keypasswd = '123abc'
            domain.use_generated_keys = True
            domain.key_passwd = dinfo.key_passwd if dinfo.key_passwd else default_keypasswd
            logs.debug(f'{domain.domain_label} key passwd is {domain.key_passwd}')

            domain.portal_ssl_pass = dinfo.portal_ssl_pass if dinfo.portal_ssl_pass else default_keypasswd
            logs.debug(f'{domain.domain_label} portal_ssl_pass is {domain.portal_ssl_pass}')

        domain.enable_setkey_env = dinfo.enable_setkey_env

        domain.deploy_dir = dinfo.deploy_dir if dinfo.deploy_dir else join(
            self._deploy.deploy_root, domain_label)

        # generate secret and genesis conf
        key_dir = self._build_file(
            f'scripts/resources/domain_keys/{self._deploy.domain_key_type}/{domain_label}')

        bls_keytype = 'bls12381'
        stabilizing_key_dir = self._build_file(
                f'scripts/resources/domain_keys/{bls_keytype}/{domain_label}')

        # 生成的Key与默认Key 命名隔离
        key_file = 'generate.key' if domain.use_generated_keys else 'new.key'
        pkey_file = 'generate.pub' if domain.use_generated_keys else 'new.pub'

        if domain.use_generated_keys:
            # generate domain key
            self._generate_prikey(self._deploy.domain_key_type, key_dir, key_file, key_passwd=domain.key_passwd)
            # generate bls key
            self._generate_prikey(bls_keytype, stabilizing_key_dir, key_file)

        else:
            if domain_label in const.PREDEFINED_DOMAINS or exists(join(key_dir, key_file)) or exists(join(key_dir, pkey_file)):
                logs.info(
                    f'use predefined domain key, or exsited key: {key_dir}/{key_file}')
            else:
                logs.info(
                    f'no predefined domain key for {domain_label}, create new key')
                local.run(f'mkdir -p {key_dir}')
                local.run(
                    f"openssl ecparam -name prime256v1 -genkey | openssl pkcs8 -topk8 -passout pass:123abc -out {join(key_dir, key_file)}")
            stabilizing_key_dir = self._build_file(
                f'scripts/resources/domain_keys/bls12381/{domain_label}')
            if not (exists(join(stabilizing_key_dir, key_file)) or exists(join(stabilizing_key_dir, pkey_file))):
                logs.fatal(
                    f'failed to use predefined stabilizing key: {stabilizing_key_dir}/{key_file}')
        domain.secret.domain.files = {
            'key': f'{key_dir}/{key_file}',
            'key_pub': f'{key_dir}/{pkey_file}',
            'stabilizing_key': f'{stabilizing_key_dir}/{key_file}',
            'stabilizing_pk': f'{stabilizing_key_dir}/{pkey_file}'
        }
        # key_type = self._deploy.client_key_type
        # domain.secret.client.files = {
        #     'ca_cert': f'../conf/resources/portal/{key_type}/client/ca.crt',
        #     'cert': f'../conf/resources/portal/{key_type}/client/client.crt',
        #     'key': f'../conf/resources/portal/{key_type}/client/client.key'
        # }
        # genesis.{chain_id}.conf 后面会生成, 这里关联上相对路径
        # domain.genesis_conf = self._genesis_file
        domain.genesis_conf = "../genesis.conf"

        # TODO 做配置检查, 实例分配，partition/msu是否可均匀分组
        # 获得所有服务实例的个数
        service_count = defaultdict(int)
        for desc in dinfo.cluster:
            for inst_name in desc.instances.split(','):
                inst_name = inst_name.strip()
                service = inst_name.rstrip(string.digits)
                service_count[service] += 1
        avr_partition = 255
        avr_msu = 255
        if const.SERVICE_LIGHT in service_count:
            self._is_light = True
        else:
            avr_partition = int(const.PARTITION_SIZE /
                                service_count[const.SERVICE_TXPOOL])
        domain_port = dinfo.domain_port
        cli_ws_port = dinfo.client_ws_port
        cli_http_port = dinfo.client_http_port #提取端口 删除冗余配置只保留http和ws

        etcd_initial_cluster = {}
        for desc in dinfo.cluster:
            advertise_host = desc.host
            # check host not 127.0.0.1
            if advertise_host == "127.0.0.1":
                logs.fatal("Please set-ip first,use pharos set-ip [public ip]")
            start_port = desc.start_port
            for inst_name in desc.instances.split(','):
                inst_name = inst_name.strip()
                instance = Instance()
                instance.name = inst_name
                instance.dir = join(domain.deploy_dir, inst_name)
                instance.service = inst_name.rstrip(string.digits)
                instance.ip = desc.deploy_ip
                idx_suffix = inst_name.lstrip(string.ascii_letters)
                idx = int(idx_suffix) if idx_suffix else 0
                rpc_port = self._start_port(start_port, instance.service) + idx

                if instance.service == const.SERVICE_ETCD:
                    instance.args = ['1>stderr 2>stdout &']
                    peer_port = rpc_port
                    client_port = peer_port + 100
                    instance.env = {
                        'ETCD_NAME': f'etcd{idx}',
                        'ETCD_DATA_DIR': '../data/etcd',
                        'ETCD_LOG_OUTPUTS': '../log/etcd.log',
                        'ETCD_ENABLE_V2': 'true',
                        'ETCD_LISTEN_PEER_URLS': f'http://0.0.0.0:{peer_port}',
                        'ETCD_INITIAL_ADVERTISE_PEER_URLS': f'http://{advertise_host}:{peer_port}',
                        'ETCD_LISTEN_CLIENT_URLS': f'http://0.0.0.0:{client_port}',
                        'ETCD_ADVERTISE_CLIENT_URLS': f'http://{advertise_host}:{client_port}'
                    }
                    etcd_initial_cluster[instance.env['ETCD_NAME']
                                         ] = instance.env['ETCD_INITIAL_ADVERTISE_PEER_URLS']
                elif instance.service == const.SERVICE_STORAGE:
                    instance.args = self._deploy.storage.args + \
                        ['-c', '../conf/svc.conf', '-d']
                    # storage: msu 均匀分组
                    start_msu = avr_msu * idx
                    stop_msu = avr_msu * (idx + 1) - 1
                    instance.env = {
                        **self._deploy.storage.env,
                        'STORAGE_ID': idx_suffix,
                        'STORAGE_RPC_LISTEN_URL': f'0.0.0.0:{rpc_port}',
                        'STORAGE_RPC_ADVERTISE_URL': f'{advertise_host}:{rpc_port}',
                        'STORAGE_MSU': f'{start_msu}-{stop_msu}'
                    }
                else:
                    instance.args = self._deploy.pharos.args + \
                        ['-s', instance.service, '-d']
                    instance.env = {
                        **self._deploy.pharos.env,
                        f'{instance.service.upper()}_ID': idx_suffix,
                        f'{instance.service.upper()}_RPC_LISTEN_URL': f'0.0.0.0:{rpc_port}',
                        f'{instance.service.upper()}_RPC_ADVERTISE_URL': f'{advertise_host}:{rpc_port}'
                    }
                    if instance.service in [const.SERVICE_CONTROLLER, const.SERVICE_DOG, const.SERVICE_LIGHT]:
                        # controller/dog/light: 单服务实例, 没有ID环境变量
                        del instance.env[f'{instance.service.upper()}_ID']
                    if instance.service in [const.SERVICE_LIGHT, const.SERVICE_PORTAL]:
                        # portal/light: client urls
                        client_urls = []
                        client_listen_urls = []
                        if cli_http_port:
                            http_port = cli_http_port + idx
                            client_urls.append(
                                f'http://{advertise_host}:{http_port}')
                            client_listen_urls.append(
                                f'http://0.0.0.0:{http_port}')
                        if cli_ws_port:
                            ws_port = cli_ws_port + idx
                            client_urls.append(
                                f'ws://{advertise_host}:{ws_port}')
                            client_listen_urls.append(
                                f'ws://0.0.0.0:{ws_port}')
                        instance.env['CLIENT_ADVERTISE_URLS'] = ','.join(
                            client_urls)
                        instance.env['CLIENT_LISTEN_URLS'] = ','.join(
                            client_listen_urls)
                        instance.env['PORTAL_UUID'] = str(100 + idx)
                    if instance.service in [const.SERVICE_DOG, const.SERVICE_LIGHT]:
                        # dog/light: 得到每个domain的domain endpoint
                        instance.env['DOMAIN_LISTEN_URLS0'] = f'tcp://0.0.0.0:{domain_port}'
                        instance.env['DOMAIN_LISTEN_URLS1'] = f'tcp://0.0.0.0:{domain_port + 1}'
                        instance.env['DOMAIN_LISTEN_URLS2'] = f'tcp://0.0.0.0:{domain_port + 2}'
                        self._domain_endpoints[domain_label] = f'tcp://{advertise_host}:{domain_port}'
                    if instance.service == const.SERVICE_TXPOOL:
                        # txpool: partition均匀分组
                        start_partition = avr_partition * idx
                        stop_partition = avr_partition * (idx + 1) - 1
                        instance.env['TXPOOL_PARTITION_LIST'] = f'{start_partition}-{stop_partition}'
                    if instance.service == const.SERVICE_LIGHT:
                        # light: hardcode storage and txpool env
                        instance.args = self._deploy.pharos.args + ['-d']
                        instance.env['STORAGE_RPC_ADVERTISE_URL'] = instance.env['LIGHT_RPC_ADVERTISE_URL']
                        instance.env['STORAGE_ID'] = '0'
                        instance.env['STORAGE_MSU'] = '0-255'
                        instance.env['TXPOOL_PARTITION_LIST'] = '0-255'

                domain.cluster[inst_name] = instance
        for instance in domain.cluster.values():
            if instance.service == const.SERVICE_ETCD:
                instance.env['ETCD_INITIAL_CLUSTER'] = ','.join(
                    [f'{k}={v}' for k, v in etcd_initial_cluster.items()])
        domain.initial_stake_in_gwei = dinfo.initial_stake_in_gwei
        return domain

    def run(self, need_genesis: bool = False):
        all_domain: Dict[str, Domain] = {}
        # generate every domain data
        for domain_label, info in self._deploy.domains.items():
            all_domain[domain_label] = self._generate_domain(
                domain_label, info)

        # 遍历所有domain，构建genesis.conf，输出domain file
        genesis_domains = {}
        domain_index = 0
        storage_slot_kvs = {}
        #stake = 1000000000000000000 # 1 ETH
        GWEI_TO_WEI = 1000000000
        total_stake_in_wei = 0
        for domain_label, domain in all_domain.items():
            key_file = self._abspath(domain.secret.domain.files['key'])
            stabilizing_pk_file = self._abspath(domain.secret.domain.files['stabilizing_pk'])

            with open(stabilizing_pk_file, 'r') as spk_file:
                spk = spk_file.read().strip()
            
            try:
                with open(domain.secret.domain.files.get('key_pub', "r")) as pk_file:
                    pubkey = pk_file.readline().strip()
                    pubkey_bytes = bytes.fromhex(f'{pubkey}')
            except Exception as e:
                # print(e)
                pubkey, pubkey_bytes = Generator._get_pubkey(self._deploy.domain_key_type, key_file, domain.key_passwd)  
            
            node_id = hashlib.sha256(bytes(pubkey_bytes)).hexdigest()
            
            genesis_domains[domain_label] = {
                'pubkey': f'0x{pubkey}',
                'stabilizing_pubkey': spk,
                'owner': 'root',
                'endpoints': [f'{self._domain_endpoints[domain_label]}'],
                'staking' : '200000000',
                'commission_rate' : '10',
                'node_id': node_id
            }

            # put proposer_id into env
            for instance in domain.cluster.values():
                instance.env["NODE_ID"] = node_id
            domain_stake_in_wei = domain.initial_stake_in_gwei * GWEI_TO_WEI
            domain_storage_slot = self._generate_domain_slots(len(all_domain),domain_index, pubkey, spk, self._domain_endpoints[domain_label], domain_stake_in_wei)
            total_stake_in_wei += domain_stake_in_wei
            domain_index += 1
            storage_slot_kvs.update(domain_storage_slot)
        # slot 5 epoch num
        epoch_base_slot = 5
        epoch_base_slot_bytes = to_bytes(epoch_base_slot).rjust(32, b'\0')
        epoch_num = 0
        epoch_num_bytes = to_bytes(epoch_num).rjust(32, b'\0')
        storage_slot_kvs["0x" + epoch_base_slot_bytes.hex()] = "0x" + epoch_num_bytes.hex()

        # slot 6 total stake
        total_stake_base_slot = 6
        total_stake_base_slot_bytes = to_bytes(total_stake_base_slot).rjust(32, b'\0')
        total_stake_bytes = int_to_big_endian(total_stake_in_wei).rjust(32, b'\0')
        storage_slot_kvs["0x" + total_stake_base_slot_bytes.hex()] = "0x" + total_stake_bytes.hex()

        # slot 7 config addr
        cfg_base_slot = 7
        cfg_base_slot_bytes = to_bytes(cfg_base_slot).rjust(32, b'\0')
        cfg_addr = "3100000000000000000000000000000000000000"
        cfg_addr_bytes = bytes.fromhex(cfg_addr).rjust(32, b'\0')
        storage_slot_kvs["0x" + cfg_base_slot_bytes.hex()] = "0x" + cfg_addr_bytes.hex()

        # add access_control and disable initializers
        intrinsic_tx_sender = "1111111111111111111111111111111111111111"
        self._generate_access_control_admin(storage_slot_kvs, self._deploy.admin_addr) # default admin
        self._generate_access_control_admin(storage_slot_kvs, intrinsic_tx_sender) # intrinsic sender
        self._generate_disable_upgradeable_contract_initializers(storage_slot_kvs)


        genesis_data = utils.load_json(self._deploy.genesis_tpl)
        genesis_data['domains'] = genesis_domains
        sys_staking_addr = '4100000000000000000000000000000000000000'
        # 非proxy代理部署
        if 'storage' not in genesis_data['alloc'][sys_staking_addr]:
            staking_storage_slot_kvs=storage_slot_kvs
        else: # proxy代理部署
            staking_storage_slot_kvs=genesis_data['alloc'][sys_staking_addr]['storage']
            staking_storage_slot_kvs.update(storage_slot_kvs)
            
        genesis_data['alloc'][sys_staking_addr]['storage'] = staking_storage_slot_kvs
        genesis_data['alloc'][sys_staking_addr]['balance'] = hex(total_stake_in_wei)

        # chain epoch duration
        # timestamp = time.time_ns() // 1000000 # not supported until python 3.7
        timestamp = int(round(time.time() * 1000))
        genesis_data['configs']['chain.epoch_start_timestamp'] = f'{timestamp}'

        # generate chaincfg storage slot
        sys_chaincfg_addr = '3100000000000000000000000000000000000000'
        storage_slot_kvs = self._generate_chaincfg_slots(genesis_data['configs'])

        # add access_control and disable initializers
        intrinsic_tx_sender = "1111111111111111111111111111111111111111"
        self._generate_access_control_admin(storage_slot_kvs, self._deploy.admin_addr) # default admin
        self._generate_access_control_admin(storage_slot_kvs, intrinsic_tx_sender) # intrinsic sender
        self._generate_disable_upgradeable_contract_initializers(storage_slot_kvs)

        # 非proxy代理部署
        if 'storage' not in genesis_data['alloc'][sys_chaincfg_addr]:
            chaincfg_storage_slot_kvs = storage_slot_kvs
        else: # proxy代理部署
            chaincfg_storage_slot_kvs=genesis_data['alloc'][sys_chaincfg_addr]['storage']
            chaincfg_storage_slot_kvs.update(storage_slot_kvs)
            
        genesis_data['alloc'][sys_chaincfg_addr]['storage'] = chaincfg_storage_slot_kvs

        # generate rule mng storage slot
        sys_rule_mng_addr = '2100000000000000000000000000000000000000'
        storage_slot_kvs = genesis_data['alloc'][sys_rule_mng_addr]['storage']
        intrinsic_tx_sender = "1111111111111111111111111111111111111111"
        self._generate_access_control_admin(storage_slot_kvs, self._deploy.admin_addr) # default admin
        self._generate_access_control_admin(storage_slot_kvs, intrinsic_tx_sender) # intrinsic sender
        self._generate_disable_upgradeable_contract_initializers(storage_slot_kvs)

        genesis_data['alloc'][sys_rule_mng_addr]['storage'] = storage_slot_kvs

        # write admin addr
        root_sys_addr = self._deploy.admin_addr
        if root_sys_addr.startswith('0x'):
            root_sys_addr = root_sys_addr[2:]  # Remove the '0x' prefix
        root_sys_slot = {}
        root_sys_slot['balance'] = '0xc097ce7bc90715b34b9f1000000000'
        root_sys_slot['nonce'] = '0x0'
        genesis_data['alloc'][root_sys_addr] = root_sys_slot

        if need_genesis:
            with open(self._abspath(self._genesis_file), 'w') as fh:
                json.dump(genesis_data, fh, indent=2)
            # 使用 admin_addr proxy_admin_addr 替换genesis.{self._deploy.chain_id}.conf中的默认值
            conf_admin_addr = self._deploy.admin_addr[2:] if self._deploy.admin_addr.startswith("0x") else self._deploy.admin_addr
            conf_proxy_admin_addr = self._deploy.proxy_admin_addr[2:] if self._deploy.proxy_admin_addr.startswith("0x") else self._deploy.proxy_admin_addr
            default_admin_addr = "2cc298bdee7cfeac9b49f9659e2f3d637e149696"
            default_proxy_admin_addr = "0278872d3f68b15156e486da1551bcd34493220d"
            # 替换分隔符为 |
            local.run(
                f'sed -i "s|{default_admin_addr}|{conf_admin_addr}|" {self._abspath(self._genesis_file)}'
            )
            local.run(
                f'sed -i "s|{default_proxy_admin_addr}|{conf_proxy_admin_addr}|" {self._abspath(self._genesis_file)}'
            )

        for domain_label, domain in all_domain.items():
            domain_data = DomainSchema().dump(domain)
            # 删除一些默认可得的信息，简化输出的domain file
            for name, instance in domain_data['cluster'].items():
                if instance['name'] == name:
                    del instance['name']
                if instance['dir'] == join(domain.deploy_dir, name):
                    del instance['dir']
            # 按服务顺序
            keys = list(domain_data['cluster'].keys())
            keys.sort()
            domain_data['cluster'] = {
                k: domain_data['cluster'][k] for k in keys}
            domain_file = self._abspath(f'{domain_label}.json')
            logs.info(f'dump {domain_label} file at: {domain_file}')
            # json.dump(domain_data, fh, indent=2)
            utils.dump_json(domain_file, domain_data, list_inline=True)
        
        # NOTE: pharos.conf generation is now disabled - using static file instead
        # Generate pharos.conf and mygrid_genesis.conf for simplified deployment
        # These files are needed by bootstrap command
        logs.info('Generating mygrid_genesis.conf...')
        # logs.info('Generating pharos.conf and mygrid_genesis.conf...')
        for domain_label, domain in all_domain.items():
            domain_file = self._abspath(f'{domain_label}.json')
            try:
                # Import Composer here to avoid circular dependency
                from pharos_ops.toolkit import core
                composer = core.Composer(domain_file)
                
                # NOTE: pharos.conf is now a static file, generation disabled
                # Generate pharos.conf to conf/ directory
                # conf_dir = self._build_file('conf')
                # pharos_conf_file = join(conf_dir, 'pharos.conf')
                # from pharos_ops.toolkit.schemas.aldaba import RootConfigSchema
                # composer._dump_json(pharos_conf_file, RootConfigSchema().dump(composer._pharos_conf))
                # logs.info(f'Generated pharos.conf at: {pharos_conf_file}')
                
                # Generate mygrid_genesis.conf to bin/ directory
                bin_dir = self._build_file('bin')
                mygrid_genesis_file = join(bin_dir, const.MYGRID_GENESIS_CONFIG_FILENAME)
                utils.dump_json(mygrid_genesis_file, composer._mygrid_client_conf)
                logs.info(f'Generated {const.MYGRID_GENESIS_CONFIG_FILENAME} at: {mygrid_genesis_file}')
            except Exception as e:
                logs.error(f'Failed to generate config files: {e}')
                raise
                  
        # 配置以最新的 SPEC VERSION 进行部署
        if self._deploy.use_latest_version:
            pharos_version_file = self._build_file('bin', const.PHAROS_VERSION)
            pharos_version_file_bak = self._build_file('bin', f"{const.PHAROS_VERSION}_bak")
                        
            # 备份文件
            if not exists(pharos_version_file_bak): 
                local.run(f'cp -rf {pharos_version_file} {pharos_version_file_bak}')

            with open(pharos_version_file, "r") as file:
                data = json.load(file)  
            max_key = max(data, key=lambda k: data[k]["version"])
            result = {max_key: data[max_key]}
            result[max_key]["epoch"] = 0
            logs.info(f'dump VERSION file at: {pharos_version_file}')
            with open(pharos_version_file, "w") as file:
                json.dump(result, file, indent=2)

    def generate_genesis(self):
        all_domain: Dict[str, Domain] = {}
        # only use first domain
        domain_label = list(self._deploy.domains.keys())[0]
        domain_file = self._abspath(f'{domain_label}.json')
        with open(domain_file, 'r') as file:
            domain_data = json.load(file)
            domain = DomainSchema().load(domain_data)
            all_domain[domain_label] = domain

        # 遍历所有domain，构建genesis.conf，输出domain file
        genesis_domains = {}
        domain_index = 0
        storage_slot_kvs = {}
        #stake = 1000000000000000000 # 1 ETH
        GWEI_TO_WEI = 1000000000
        total_stake_in_wei = 0
        for domain_label, domain in all_domain.items():
            key_file = self._abspath(domain.secret.domain.files['key'])
            stabilizing_pk_file = self._abspath(domain.secret.domain.files['stabilizing_pk'])

            with open(stabilizing_pk_file, 'r') as spk_file:
                spk = spk_file.read().strip()
            
            try:
                with open(domain.secret.domain.files.get('key_pub', "r")) as pk_file:
                    pubkey = pk_file.readline().strip()
                    pubkey_bytes = bytes.fromhex(f'{pubkey}')
            except Exception as e:
                # print(e)
                pubkey, pubkey_bytes = Generator._get_pubkey(self._deploy.domain_key_type, key_file, domain.key_passwd)  
            
            node_id = hashlib.sha256(bytes(pubkey_bytes)).hexdigest()
            domain_host = self._deploy.domains[domain_label].cluster[0].host
            domain_port = self._deploy.domains[domain_label].domain_port
            endpoint = f"tcp://{domain_host}:{domain_port}"
            genesis_domains[domain_label] = {
                "pubkey": f"0x{pubkey}",
                "stabilizing_pubkey": spk,
                "owner": "root",
                "endpoints": [endpoint],
                "staking": "200000000",
                "commission_rate": "10",
                "node_id": node_id,
            }
            # put proposer_id into env
            for instance in domain.cluster.values():
                instance.env["NODE_ID"] = node_id
            domain_stake_in_wei = domain.initial_stake_in_gwei * GWEI_TO_WEI
            domain_storage_slot = self._generate_domain_slots(len(all_domain),domain_index, pubkey, spk, endpoint, domain_stake_in_wei)
            total_stake_in_wei += domain_stake_in_wei
            domain_index += 1
            storage_slot_kvs.update(domain_storage_slot)
        # slot 5 epoch num
        epoch_base_slot = 5
        epoch_base_slot_bytes = to_bytes(epoch_base_slot).rjust(32, b'\0')
        epoch_num = 0
        epoch_num_bytes = to_bytes(epoch_num).rjust(32, b'\0')
        storage_slot_kvs["0x" + epoch_base_slot_bytes.hex()] = "0x" + epoch_num_bytes.hex()

        # slot 6 total stake
        total_stake_base_slot = 6
        total_stake_base_slot_bytes = to_bytes(total_stake_base_slot).rjust(32, b'\0')
        total_stake_bytes = int_to_big_endian(total_stake_in_wei).rjust(32, b'\0')
        storage_slot_kvs["0x" + total_stake_base_slot_bytes.hex()] = "0x" + total_stake_bytes.hex()

        genesis_data = utils.load_json(self._deploy.genesis_tpl)
        genesis_data['domains'] = genesis_domains
        sys_staking_addr = '4100000000000000000000000000000000000000'
        # 非proxy代理部署
        if 'storage' not in genesis_data['alloc'][sys_staking_addr]:
            staking_storage_slot_kvs=storage_slot_kvs
        else: # proxy代理部署
            staking_storage_slot_kvs=genesis_data['alloc'][sys_staking_addr]['storage']
            staking_storage_slot_kvs.update(storage_slot_kvs)
            
        genesis_data['alloc'][sys_staking_addr]['storage'] = staking_storage_slot_kvs
        genesis_data['alloc'][sys_staking_addr]['balance'] = hex(total_stake_in_wei)

        # chain epoch duration
        # timestamp = time.time_ns() // 1000000 # not supported until python 3.7
        timestamp = int(round(time.time() * 1000))
        genesis_data['configs']['chain.epoch_start_timestamp'] = f'{timestamp}'

        # generate chaincfg storage slot
        sys_chaincfg_addr = '3100000000000000000000000000000000000000'
        storage_slot_kvs = self._generate_chaincfg_slots(genesis_data['configs'])
        # 非proxy代理部署
        if 'storage' not in genesis_data['alloc'][sys_chaincfg_addr]:
            chaincfg_storage_slot_kvs = storage_slot_kvs
        else: # proxy代理部署
            chaincfg_storage_slot_kvs=genesis_data['alloc'][sys_chaincfg_addr]['storage']
            chaincfg_storage_slot_kvs.update(storage_slot_kvs)
            
        genesis_data['alloc'][sys_chaincfg_addr]['storage'] = chaincfg_storage_slot_kvs

        # generate rule mng storage slot
        sys_rule_mng_addr = '2100000000000000000000000000000000000000'
        storage_slot_kvs = self._generate_rule_mng_slots(genesis_data['alloc'][sys_rule_mng_addr]['storage'])
        genesis_data['alloc'][sys_rule_mng_addr]['storage'] = storage_slot_kvs

        # write admin addr
        root_sys_addr = self._deploy.admin_addr
        if root_sys_addr.startswith('0x'):
            root_sys_addr = root_sys_addr[2:]  # Remove the '0x' prefix
        root_sys_slot = {}
        root_sys_slot['balance'] = '0xc097ce7bc90715b34b9f1000000000'
        root_sys_slot['nonce'] = '0x0'
        genesis_data['alloc'][root_sys_addr] = root_sys_slot

        with open(self._abspath(self._genesis_file), 'w') as fh:
            json.dump(genesis_data, fh, indent=2)
        # 使用 admin_addr proxy_admin_addr 替换genesis.{self._deploy.chain_id}.conf中的默认值
        conf_admin_addr = self._deploy.admin_addr[2:] if self._deploy.admin_addr.startswith("0x") else self._deploy.admin_addr
        conf_proxy_admin_addr = self._deploy.proxy_admin_addr[2:] if self._deploy.proxy_admin_addr.startswith("0x") else self._deploy.proxy_admin_addr
        default_admin_addr = "2cc298bdee7cfeac9b49f9659e2f3d637e149696"
        default_proxy_admin_addr = "0278872d3f68b15156e486da1551bcd34493220d"
        # 替换分隔符为 |
        local.run(
            f'sed -i "s|{default_admin_addr}|{conf_admin_addr}|" {self._abspath(self._genesis_file)}'
        )
        local.run(
            f'sed -i "s|{default_proxy_admin_addr}|{conf_proxy_admin_addr}|" {self._abspath(self._genesis_file)}'
        )
