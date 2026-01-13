#!/usr/bin/env python3
# coding=utf-8
"""
    Copyright (C) 2020 Pharos Labs. All rights reserved.

    Desc     : Pharos2.0 Operation Tools
    History  :
    License  : Pharos Labs proprietary/confidential.

    Python Version : 3.6.8
    Created by youxing.zys
    Date: 2022/12/06
"""
from multiprocessing import Process
from functools import wraps
from typing import List

from pharos_ops.toolkit import conf, core, logs
import traceback
import subprocess
import os
from pharos_ops.toolkit.conn_group import local
import shutil
from .schemas import DeploySchema
import json

def catch_exception(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logs.error(f'{e}')
            pass
    return wrapped


@catch_exception
def generate_keys(output_dir: str, key_passwd: str = "123abc"):
    """
    Command: pharos-ops generate-keys
    Generate domain keys (prime256v1 and bls12381) to specified directory
    """
    import os
    from os.path import join, exists
    from pharos_ops.toolkit.conn_group import local
    from pharos_ops.toolkit import const
    
    # Create output directory if not exists
    if not exists(output_dir):
        os.makedirs(output_dir)
        logs.info(f'Created directory: {output_dir}')
    
    # Generate prime256v1 key (domain key)
    logs.info('Generating prime256v1 key...')
    prime256v1_key = join(output_dir, 'domain.key')
    prime256v1_pub = join(output_dir, 'domain.pub')
    
    local.run(f"openssl ecparam -name prime256v1 -genkey | openssl pkcs8 -topk8 -outform pem -out {prime256v1_key} -v2 aes-256-cbc -v2prf hmacWithSHA256 -passout pass:{key_passwd}")
    
    # Get public key
    from pharos_ops.toolkit.conf import Generator
    pubkey, _ = Generator._get_pubkey('prime256v1', prime256v1_key, key_passwd)
    local.run(f"echo {pubkey} > {prime256v1_pub}")
    logs.info(f'Generated prime256v1 key: {prime256v1_key}')
    logs.info(f'Generated prime256v1 pub: {prime256v1_pub}')
    
    # Generate bls12381 key (stabilizing key)
    logs.info('Generating bls12381 key...')
    bls_key = join(output_dir, 'stabilizing.key')
    bls_pub = join(output_dir, 'stabilizing.pub')
    
    # Find pharos_cli
    pharos_cli_path = None
    evmone_so_path = None
    
    # Try to find pharos_cli in common locations
    possible_paths = [
        '../bin/pharos_cli',
        './bin/pharos_cli',
        'bin/pharos_cli'
    ]
    
    for path in possible_paths:
        if exists(path):
            pharos_cli_path = path
            evmone_so_dir = os.path.dirname(path)
            evmone_so_path = join(evmone_so_dir, 'libevmone.so')
            break
    
    if not pharos_cli_path or not exists(pharos_cli_path):
        logs.error('pharos_cli not found. Please ensure pharos_cli is in ../bin/ or ./bin/')
        return
    
    # Generate BLS key using pharos_cli
    ret = local.run(f"LD_PRELOAD={evmone_so_path} {pharos_cli_path} crypto -t gen-key -a bls12381 | tail -n 2")
    bls_prikey = ret.stdout.split()[0].split(':')[1]
    bls_pubkey = ret.stdout.split()[1].split(':')[1]
    
    local.run(f"echo {bls_prikey} > {bls_key}")
    local.run(f"echo {bls_pubkey} > {bls_pub}")
    logs.info(f'Generated bls12381 key: {bls_key}')
    logs.info(f'Generated bls12381 pub: {bls_pub}')
    
    logs.info(f'\nKeys generated successfully in: {output_dir}')
    logs.info('Files created:')
    logs.info(f'  - domain.key (prime256v1 private key)')
    logs.info(f'  - domain.pub (prime256v1 public key)')
    logs.info(f'  - stabilizing.key (bls12381 private key)')
    logs.info(f'  - stabilizing.pub (bls12381 public key)')


@catch_exception
def encode_key(key_path: str):
    """
    Command: pharos-ops encode-key
    Encode key file to base64 format for use in pharos.conf
    """
    print(f"encoded key: {core.to_base64(key_path)}")


@catch_exception
def encode_key_to_conf(key_path: str, pharos_conf: str, key_type: str):
    """
    Command: pharos-ops encode-key-to-conf
    Encode key file to base64 and write to pharos.conf
    """
    import json
    from os.path import exists
    
    # Check if pharos.conf exists
    if not exists(pharos_conf):
        logs.error(f'pharos.conf not found: {pharos_conf}')
        return
    
    # Encode key
    encoded_key = core.to_base64(key_path)
    logs.info(f'Encoded key: {encoded_key}')
    
    # Read pharos.conf
    with open(pharos_conf, 'r') as f:
        pharos_data = json.load(f)
    
    # Update the appropriate key field
    if 'aldaba' not in pharos_data:
        pharos_data['aldaba'] = {}
    if 'secret_config' not in pharos_data['aldaba']:
        pharos_data['aldaba']['secret_config'] = {}
    
    if key_type == 'domain':
        pharos_data['aldaba']['secret_config']['domain_key'] = encoded_key
        logs.info('Updated domain_key in pharos.conf')
    elif key_type == 'stabilizing':
        pharos_data['aldaba']['secret_config']['stabilizing_key'] = encoded_key
        logs.info('Updated stabilizing_key in pharos.conf')
    
    # Write back to pharos.conf
    with open(pharos_conf, 'w') as f:
        json.dump(pharos_data, f, indent=2)
    
    logs.info(f'Successfully updated {pharos_conf}')


@catch_exception
def generate(deploy_file: str, need_genesis: bool = False, key_passwd: str = ""):
    """
    Command: pharos-ops configure
    """

    generator = conf.Generator(deploy_file, key_passwd)
    generator.run(need_genesis)

@catch_exception
def generate_genesis(deploy_file: str):
    """
    Command: pharos-ops generate-genesis
    """
    generator = conf.Generator(deploy_file)
    generator.generate_genesis()

# Deploy, update, and update_conf functions removed
# New simplified flow: generate -> bootstrap -> start
# Management directory is now the deployment directory
            
            
@catch_exception
def clone(src_domain: str, dest_domains: List[str], is_cold: bool, backup: bool):
    """
    Command: pharos-ops clone
    """
    
    src_composer = core.Composer(src_domain)
    try:
        placement_info = src_composer.clone_from(is_cold)
        
        for dest_domain in dest_domains:
            composer = core.Composer(dest_domain)
            composer.clone_to(placement_info, backup)

    except Exception as e:
        error_msg = traceback.format_exc()
        print(error_msg)


@catch_exception
def update_validator(endpoint, key, domains, poolId, new_owner):
    """
    Command: pharos-ops update-validator
    """
    for domain in domains:
        composer = core.Composer(domain)
        composer.update_validator(endpoint, key, poolId, new_owner)


@catch_exception
def add_validator(endpoint, key, domains):
    """
    Command: pharos-ops add-validator
    """
    for domain in domains:
        composer = core.Composer(domain)
        composer.add_validator(endpoint, key)
    

@catch_exception
def exit_validator(endpoint, key, domains):
    """
    Command: pharos-ops exit-validator
    """
    
    for domain in domains:
        compose = core.Composer(domain)
        compose.exit_validator(endpoint, key)
    

@catch_exception
def clean(domain_files: str, service: str, all: bool):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.clean(service, all)


@catch_exception
def bootstrap(domain_files: str):
    """
    Command: pharos-ops bootstrap
    """
    # for domain_file in domain_files:
    #     composer = core.Composer(domain_file)
    #     composer.bootstrap()
    if len(domain_files) == 1:
        composer = core.Composer(domain_files[0])
        composer.bootstrap()
    else:
        procs = []
        for domain_file in domain_files:
            composer = core.Composer(domain_file)
            p = Process(target=composer.bootstrap)
            procs.append(p)
            p.start()
        for p in procs:
            p.join()


@catch_exception
def bootstrap_simple():
    """
    Command: pharos-ops bootstrap (simplified version without domain.json)
    Executes bootstrap directly without needing domain.json file
    """
    logs.info('Starting simplified bootstrap')
    
    # Execute bootstrap directly without Composer
    from os.path import join, abspath, exists
    from pharos_ops.toolkit.conn_group import local
    from pharos_ops.toolkit import const
    
    # Assume we're in the management directory (scripts/)
    # Directory structure: bin/, conf/, data/, genesis.conf, log/
    bin_dir = abspath('../bin')
    genesis_file = abspath('../genesis.conf')
    pharos_conf_file = abspath('../conf/pharos.conf')
    
    # Check if genesis.conf exists
    if not exists(genesis_file):
        logs.error(f'Genesis file not found: {genesis_file}')
        return
    
    # Check if pharos.conf exists
    if not exists(pharos_conf_file):
        logs.error(f'Config file not found: {pharos_conf_file}')
        return
    
    # NOTE: mygrid_genesis.conf is no longer required
    # The configuration is now embedded in pharos.conf
    
    # Execute pharos_cli genesis locally
    cmd = f'cd {bin_dir}; LD_PRELOAD=./libevmone.so ./pharos_cli genesis -g ../genesis.conf -c ../conf/pharos.conf'
    logs.info(f'Executing locally: {cmd}')
    result = local.run(cmd)
    if not result.ok:
        logs.error(f'Bootstrap failed: {result.stderr}')
    else:
        logs.info('Bootstrap completed successfully')


@catch_exception
def status(domain_files: str, service: str):
    """
    Command: pharos-ops status
    """

    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.status(service)
        
@catch_exception
def diff(domain1: str, domain2: str, start: str, statefork: bool):
    """
    Command: pharos-ops diff
    """
    composer1 = core.Composer(domain1)
    composer2 = core.Composer(domain2)
    if statefork:
        core.diffstatefork(composer1, composer2, start)
    else:
        core.diff(composer1, composer2, start)
    
@catch_exception
def query(domain, type, arg):
    composer = core.Composer(domain)
    
    if type == 'stable_block_number':
        result = composer.get_stable_block_num()
    elif type == 'written_block_number':
        result = composer.get_written_block_num()
    elif type == 'block':
        result = composer.get_block_by_num(int(arg[0], 10))
    elif type == 'block_by_hash':
        result = composer.get_block_by_hash(arg[0])
    elif type == 'tx':
        result = composer.get_tx(arg[0])
    elif type == 'receipt':
        result = composer.get_receipt(arg[0])
    elif type == 'code':
        result = composer.get_code(arg[0])
    elif type == 'nonce':
        result = composer.get_nonce(arg[0])
    elif type == 'balance':
        result = composer.get_balance(arg[0])
    else:
        logs.error(f"Unknown query type: {type}")
        return
    
    if not result is None:
        print(result)
    else:
        logs.error("Failed to query")
    

@catch_exception
def start(domain_files: str, service: str, extra_storage_args: str):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.start(service, extra_storage_args)


@catch_exception
def start_simple(service: str = None, extra_storage_args: str = ''):
    """
    Command: pharos-ops start (simplified version without domain.json)
    Starts services directly without needing domain.json file
    """
    logs.info('Starting services (simplified mode)')
    
    from os.path import abspath, exists, join
    from pharos_ops.toolkit.conn_group import local
    
    # Assume we're in the management directory (scripts/)
    # For light mode, we start the pharos_light service directly
    bin_dir = abspath('../bin')
    pharos_conf_file = abspath('../conf/pharos.conf')
    
    # Check if pharos.conf exists
    if not exists(pharos_conf_file):
        logs.error(f'Config file not found: {pharos_conf_file}')
        return
    
    # Start pharos_light service
    # Assuming light mode deployment
    work_dir = bin_dir
    
    # Check if libevmone.so exists
    evmone_so = join(bin_dir, 'libevmone.so')
    pharos_light = join(bin_dir, 'pharos_light')
    
    if not exists(pharos_light):
        logs.error(f'pharos_light binary not found: {pharos_light}')
        return
    
    # Start the service
    if exists(evmone_so):
        cmd = f"cd {work_dir}; LD_PRELOAD=./libevmone.so ./pharos_light -c ../conf/pharos.conf -d"
    else:
        cmd = f"cd {work_dir}; ./pharos_light -c ../conf/pharos.conf -d"
    
    logs.info(f'Starting pharos_light: {cmd}')
    result = local.run(cmd)
    
    if result.ok:
        logs.info('Services started successfully')
    else:
        logs.error(f'Failed to start services: {result.stderr}')


@catch_exception
def restart(domain_files: str, service: str, extra_storage_args: str):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.stop(service)
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.start(service, extra_storage_args)


@catch_exception
def stop(domain_files: str, service: str, force=False):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.stop(service, force)


@catch_exception
def stop_simple(service: str = None, force: bool = False):
    """
    Command: pharos-ops stop (simplified version without domain.json)
    Stops services directly without needing domain.json file
    """
    logs.info(f'Stopping services (simplified mode), service: {service}, force: {force}')
    
    from os.path import abspath, exists, join
    from pharos_ops.toolkit.conn_group import local
    import subprocess
    
    # Assume we're in the management directory (scripts/)
    # For light mode, we stop the pharos_light service directly
    bin_dir = abspath('../bin')
    
    # Find and kill pharos_light process
    # Use ps to find the process
    try:
        # Find pharos_light process
        cmd = "ps -eo pid,cmd | grep pharos_light | grep -v grep | awk '{print $1}'"
        result = local.run(cmd, hide=True)
        
        if result.ok and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    if force:
                        # Force kill with SIGKILL
                        kill_cmd = f'kill -9 {pid}'
                        logs.info(f'Force stopping pharos_light (PID: {pid})')
                    else:
                        # Graceful kill with SIGTERM
                        kill_cmd = f'kill -15 {pid}'
                        logs.info(f'Gracefully stopping pharos_light (PID: {pid})')
                    
                    kill_result = local.run(kill_cmd, warn=True)
                    if kill_result.ok:
                        logs.info(f'Successfully stopped process {pid}')
                    else:
                        logs.error(f'Failed to stop process {pid}')
            
            logs.info('Services stopped successfully')
        else:
            logs.info('No pharos_light process found')
    except Exception as e:
        logs.error(f'Failed to stop services: {e}')


@catch_exception
def upgrade():
    """
    Command: pharos-ops upgrade
    """
    fh = open("./deploy.light.json", "r")
    deploy_data = json.load(fh)
    deploy = DeploySchema().load(deploy_data)

    deploy_path = f"{deploy.deploy_root}"
    original_cwd = os.getcwd()
    logs.info(f"original_cwd: {original_cwd}")
    logs.info(f"deploy_path: {deploy_path}")
    files_to_remove = [
        f"{deploy_path}/domain/light/bin/libevmone.so",
        f"{deploy_path}/domain/light/bin/pharos_light",
        f"{deploy_path}/domain/light/bin/VERSION",
        f"{deploy_path}/domain/client/bin/pharos_cli",
    ]
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)

    symlinks = [
        (
            f"{original_cwd}/../bin/libevmone.so",
            f"{deploy_path}/domain/light/bin/libevmone.so",
        ),
        (
            f"{original_cwd}/../bin/pharos_light",
            f"{deploy_path}/domain/light/bin/pharos_light",
        ),
        (
            f"{original_cwd}/../bin/VERSION",
            f"{deploy_path}/domain/light/bin/VERSION",
        ),
    ]
    for src, dst in symlinks:
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(src, dst)

    try:
        # shutil.copyfile(
        #     f"{deploy_path}/domain/light/conf/monitor.conf",
        #     f"{original_cwd}/../conf/monitor.conf",
        # )

        shutil.copyfile(
            f"{original_cwd}/../bin/pharos_cli",
            f"{deploy_path}/domain/client/bin/pharos_cli",
        )
    except Exception as e:
        logs.error(f"Upgrade failed: {e}")
    finally:
        os.chdir(original_cwd)
