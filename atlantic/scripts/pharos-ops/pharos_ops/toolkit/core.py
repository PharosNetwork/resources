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
import json
import copy
import base64
import yaml
import tempfile
import time
import os
import sys
import requests
import random

from hexbytes import HexBytes
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple
from os.path import join, abspath, isabs, dirname, basename
from invoke import Context
from patchwork.files import exists
from fabric.connection import Connection
from pathlib import Path
import hashlib
from web3 import Web3
from eth_account import Account
from datetime import datetime
from tempfile import NamedTemporaryFile

from pharos_ops.toolkit import command, svc, const, logs, utils
from pharos_ops.toolkit.schemas.domain import *
from pharos_ops.toolkit.conn_group import is_local, ConcurrentGroup, local
from pharos_ops.toolkit.utils import safe_get_nested
from pharos_ops.toolkit.conf import Generator

def to_base64(file: str):
    with open(file, 'r') as fp:
        bcontent = fp.read().encode()
        return base64.b64encode(bcontent).decode()


def load_file(file: str):
    with open(file, 'r') as fp:
        return fp.read()


def clean_folder(conn: Connection, folder: str, except_: str = None):
    if folder == "/":
        logs.error("Error: Attempted to clean the root directory. Operation aborted.")
        sys.exit(1)

    if not exists(conn, folder):
        return

    logs.info(f'clean folder: {folder} on {conn.host}')

    if except_:
        cmd = f'cd {folder}; find . -maxdepth 1 ! -path . ! -name {except_} -print0 |' + \
            'xargs -0 -I {} rm -rf {}'
    else :
        cmd = f'cd {folder};' + \
            'find . -maxdepth 1 ! -path . -print0 | xargs -0 -I {} rm -rf {}'
    conn.run(cmd)

def clean_file(conn: Connection, file: str, except_: str = None):
    if file == "/":
        logs.error("Error: Attempted to clean the root. Operation aborted.")
        sys.exit(1)

    if not exists(conn, file):
        return

    logs.info(f'clean file: {file} on {conn.host}')

    conn.run(f'rm -rf {file}')

def extract_mygrid_placements(json_data):
    placement_paths = set()
    project_data_path = json_data['mygrid_env']['project_data_path']
    placements = json_data['mygrid_env'].get('placements', [])
    for placement in placements:
        for key, value in placement.items():
            if isinstance(value, list):
                for item in value:
                    placement_paths.add(f"{item}/{project_data_path}")
            else:
                placement_paths.add(f"{value}/{project_data_path}")

    return list(placement_paths)

def extract_mygrid_placements_with_key(json_data) -> Tuple[Dict[str, List[str]], str]:
    logs.debug("extract mygrid placement, input json=" + str(json_data))
    placement_paths: dict[str, List[str]] = defaultdict(list)
    project_data_path = json_data['mygrid_env']['project_data_path']
    placements = json_data['mygrid_env'].get('placements', [])
    for placement in placements:
        for key, value in placement.items():
            if isinstance(value, list):
                for item in value:
                    placement_paths[key].append(item)
            else:
                placement_paths[key].append(value)

    return (placement_paths, project_data_path)

# Generate the database placement map between domains
def generate_interdomain_placements_map(placements_1: Dict[str, List[str]], placements_2: Dict[str, List[str]]):
    placements_map: dict[str, str] = {}
    for key, value1 in placements_1.items():
        value2 = placements_2.get(key)
        if not isinstance(value1, type(value2)):
            return None

        if isinstance(value1, list):
            if  len(value1) != len(value2):
                return None
            for index, path in enumerate(value1):
                current_map = placements_map.get(path)
                # if no map found, create a new map relation
                if current_map is None:
                    placements_map[path] = value2[index]
                # more than one map is invalid
                elif current_map != value2[index]:
                    return None
        else:
            current_map = placements_map.get(value1)
            # if no map found, create a new map
            if current_map is None:
                placements_map[value1] = value2
            # more than one map is invalid
            elif current_map != value2:
                return None

    return placements_map



class Composer(object):
    """Manager class to execute command with $domain_label.json"""

    def __init__(self, domain_file: str):
        self._domain_file_path = dirname(abspath(domain_file))
        self._domain_file_data = utils.load_json(domain_file)
        self._domain: Domain = DomainSchema().load(self._domain_file_data)
        self._domain.build_root = self._abspath(self._domain.build_root)
        self._domain.domain_index = self._domain.domain_label[6:]
        if not self._domain.domain_index:
            self._domain.domain_index = '0'

        self.parse_metrics_config()

        self._extra_storage_start_args: str = ''
        self._is_light: bool = False
        self._all_instances: Dict[str, List[Instance]]
        self._client_endpoints: List[str] = []
        self._jsonrpc_endpoint: str = ''
        self._domain_ip: str = ''
        self._domain_port: str = ''
        self._ws_ip: str = ''
        self._ws_port: str = ''
        # etcd cluster and storage nodes for generate env.json
        self._etcd_cluster: List[svc.EtcdNode] = []
        self._storage_nodes: Dict[str, svc.StorageNode] = {}
        # svc.conf
        self._mygrid_client_conf = json.loads(const.MYGRID_CLIENT_JSON)
        self._meta_conf = json.loads(const.META_SERVICE_JSON)
        self._cli_conf = json.loads(const.CLI_JSON)
        self._mygrid_conf_json = utils.load_json(f'../conf/{const.MYGRID_CONF_JSON_FILENAME}')
        self._monitor_conf_json = utils.load_json(f'../conf/{const.MONITOR_CONF_JSON_FILENAME}')
        self._dc_data = {}

        # TODO 检查配置, 比如
        # build_root检查安装包
        # 关联的文件是否存在，关联hash？
        # 检查免密连接可达性
        # 检查当前是否有genesis进程

        # ========数据解析以及默认值设定=========
        # 对于未配置的secret file，根据key_type使用默认的key files (即deploy_type=dev)
        key_file = 'generate.key' if self._domain.use_generated_keys else 'new.key'
        pkey_file = 'generate.pub' if self._domain.use_generated_keys else 'new.pub'
        
        if self.domain_secret.files.get('key') is None:
            self.domain_secret.files[
                'key'] = f'../scripts/resources/domain_keys/{self.domain_secret.key_type}/{self.domain_label}/{key_file}'
            self.domain_secret.files['key_pub'] = f'../scripts/resources/domain_keys/{self.domain_secret.key_type}/{self.domain_label}/{pkey_file}'
        if self.domain_secret.files.get('stabilizing_key') is None:
            self.domain_secret.files[
                'stabilizing_key'] = f'../scripts/resources/domain_keys/bls12381/{self.domain_label}/{key_file}'

        key_type = self.client_secret.key_type
        if self.client_secret.files.get('ca_cert') is None:
            self.client_secret.files[
                'ca_cert'] = f'../conf/resources/portal/{key_type}/client/ca.crt'
        if self.client_secret.files.get('cert') is None:
            self.client_secret.files[
                'cert'] = f'../conf/resources/portal/{key_type}/client/client.crt'
        if self.client_secret.files.get('key') is None:
            self.client_secret.files['key'] = f'../conf/resources/portal/{key_type}/client/client.key'

        # 所有关联文件转为绝对路径
        self.domain_secret.files['key'] = self._abspath(
            self.domain_secret.files['key'])
        self.domain_secret.files['key_pub'] = self._abspath(
            self.domain_secret.files['key_pub'])
        self.domain_secret.files['stabilizing_key'] = self._abspath(
            self.domain_secret.files['stabilizing_key'])
        self.client_secret.files['ca_cert'] = self._abspath(
            self.client_secret.files['ca_cert'])
        self.client_secret.files['cert'] = self._abspath(
            self.client_secret.files['cert'])
        self.client_secret.files['key'] = self._abspath(
            self.client_secret.files['key'])
        self._domain.genesis_conf = self._abspath(self._domain.genesis_conf)

        # 用于生成etcd token, 所有etcd实例共享
        ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        # 遍历cluster, 补充默认信息
        for name, instance in self._domain.cluster.items():
            # instance name should same with cluster key
            instance.name = name
            # 设置instance.dir的默认值，light: $deploy_dir/$instance.name, ultra: $deploy_dir
            if not instance.dir:
                instance.dir = join(self.deploy_dir, name)

            # include common env/log/config
            default_env = {}
            if instance.service not in [const.SERVICE_ETCD, const.SERVICE_STORAGE]:
                default_env = {
                    "SERVICE": instance.service,
                    "CHAIN_ID": self.chain_id,
                    "DOMAIN_LABEL": self.domain_label
                }
            instance.env = {**default_env, **
                            self._domain.common.env, **instance.env}
            instance.log = {**self._domain.common.log, **instance.log}
            instance.config = {**self._domain.common.config, **instance.config}
            instance.gflags = {**self._domain.common.gflags, **instance.gflags}

            # get portal client endpoints
            if instance.service in [const.SERVICE_PORTAL, const.SERVICE_LIGHT]:
                for url in [url.strip() for url in instance.env['CLIENT_ADVERTISE_URLS'].split(',')]:
                    if url.startswith('tls') or url.startswith('tcp'):
                        self._client_endpoints.append(url.split('//')[-1])
                    if url.startswith('http'):
                        self._jsonrpc_endpoint = url
            if instance.service in [const.SERVICE_PORTAL, const.SERVICE_LIGHT]:
                for url in [url.strip() for url in instance.env['CLIENT_ADVERTISE_URLS'].split(',')]:
                    if url.startswith('ws'):
                        self._ws_ip, self._ws_port = url.split('//')[-1].split(':')
                        break
            if instance.service in [const.SERVICE_PORTAL, const.SERVICE_LIGHT]:
                self._domain_ip = instance.ip
                self._domain_port = instance.env['DOMAIN_LISTEN_URLS0'].split('//')[-1].split(':')[-1]

            # generate etcd token
            if instance.service == const.SERVICE_ETCD:
                instance.env['ETCD_INITIAL_CLUSTER_TOKEN'] = f'etcd_token_{self.domain_label}_{ts}'

        # 遍历cluster, 提取etcd, storage信息
        for name, instance in self._domain.cluster.items():
            # get etcd cluster
            if instance.service == const.SERVICE_ETCD:
                # 取advertise ip/port
                ip, port = instance.env['ETCD_ADVERTISE_CLIENT_URLS'].split(
                    '//')[-1].split(':')
                peer_port = instance.env['ETCD_INITIAL_ADVERTISE_PEER_URLS'].split(
                    '//')[-1].split(':')[-1]
                node = svc.EtcdNode(ip=ip, port=port, peer_port=peer_port,
                                    deploydir=instance.dir, user=self._domain.run_user)
                self._etcd_cluster.append(node)

            if instance.service in [const.SERVICE_STORAGE, const.SERVICE_LIGHT]:
                ip, port = instance.env[f'STORAGE_RPC_ADVERTISE_URL'].split(
                    ':')
                node = svc.StorageNode(ip=ip, port=port,
                                       rest_port=None, msu=instance.env['STORAGE_MSU'],
                                       myid=int(instance.env['STORAGE_ID']), deploydir=instance.dir, user=self.run_user)
                self._storage_nodes[name] = node

        # 按照host分组所有服务实例
        if const.SERVICE_LIGHT in self._domain.cluster:
            self._is_light = True

        # parse protocl
        if self._domain.chain_protocol in [const.PROTOCOL_ALL, const.PROTOCOL_NATIVE, const.PROTOCOL_EVM]:
            self._chain_protocol = self._domain.chain_protocol
        else:
            raise ValueError(f"Invalid value for 'chain_protocol', it must be [{const.PROTOCOL_ALL}, {const.PROTOCOL_NATIVE}, {const.PROTOCOL_EVM}]: {self._domain.chain_protocol}")

        all_instances = defaultdict(list)  # host -> [instance,]
        for instance in self._domain.cluster.values():
            all_instances[instance.ip].append(instance)
        self._all_instances = dict(all_instances)

        # 配置 mygrid client config
        self.deploy_top_dir, self.meta_svc_dir = os.path.split(self.deploy_dir)
        self.deploy_top_dir, sub_dir_path = os.path.split(self.deploy_top_dir)
        self.meta_svc_dir = os.path.join(sub_dir_path, self.meta_svc_dir)

        self._mygrid_client_conf[const.MYGRID_CONFIG_NAME]['mygrid_env_path'] = f'../conf/{const.MYGRID_ENV_JSON_FILENAME}'
        self._mygrid_client_conf[const.MYGRID_CONFIG_NAME]['mygrid_conf_path'] = f'../conf/{const.MYGRID_CONF_JSON_FILENAME}'
        if self._is_light:
            self._mygrid_client_conf[const.MYGRID_CONFIG_NAME]['mygrid_client_deploy_mode'] = f'{const.LIGHT_DEPLOY_MODE}'
        else:
            self._mygrid_client_conf[const.MYGRID_CONFIG_NAME]['mygrid_client_deploy_mode'] = f'{const.ULTRA_DEPLOY_MODE}'

        if self._is_light:
            if self._domain.cluster[const.SERVICE_LIGHT].dir:
                relative_path = os.path.relpath(self._domain.cluster[const.SERVICE_LIGHT].dir, self.deploy_top_dir)
                self.meta_svc_dir = f'{relative_path}/data'
            else:
                self.meta_svc_dir = f'{self.meta_svc_dir}/light/data'
        else:
            self.meta_svc_dir = f'{self.meta_svc_dir}/data'

        # 配置 mygrid.env.json
        self._mygrid_env_json = utils.load_json(self._domain.mygrid.env.filepath)

        if self._domain.mygrid.env.enable_adaptive:
            self._mygrid_env_json["mygrid_env"]["meta_store_disk"] = self.deploy_top_dir
            self._mygrid_env_json["mygrid_env"]["project_data_path"] = self.meta_svc_dir

            # ultra, TODO......
            if self._is_light:
                placements_json_str = f'''
                [
                    {{
                        "default":"{self.deploy_top_dir}",
                        "tier_0":"{self.deploy_top_dir}"
                    }}
                ]
                '''
            else:
                placements_json_str = f'''
                [
                    {{
                        "server_idxs": [0],
                        "default":"{self.deploy_top_dir}",
                        "tier_0":"{self.deploy_top_dir}"
                    }}
                ]
                '''

            placements_json_obj = json.loads(placements_json_str)
            self._mygrid_env_json["mygrid_env"]["placements"] = placements_json_obj


            mygrid_master_port = 23100 + (int(self._domain.domain_index) * 1000)
            mygrid_server_port = 23101 + (int(self._domain.domain_index) * 1000)
            self._mygrid_env_json["mygrid_env"]["master_lite_admin_port"] = mygrid_master_port
            self._mygrid_env_json["mygrid_env"]["server_lite_admin_port"] = mygrid_server_port

            if not self._is_light:
                mygrid_service_ip = self.cluster[const.SERVICE_CONTROLLER].ip
                self._mygrid_env_json["mygrid_env"]["cluster"]["master"]["address"] = f'{mygrid_service_ip}:{mygrid_master_port}'
                self._mygrid_env_json["mygrid_env"]["cluster"]["servers"][0]["address"] = f'{mygrid_service_ip}:{mygrid_server_port}'

        # 配置meta_service.conf
        metasvc_path = f"{self._mygrid_env_json['mygrid_env']['meta_store_disk']}/{self._mygrid_env_json['mygrid_env']['project_data_path']}"
        etcd_conf = self._meta_conf[const.META_SERVICE_CONFIG_NAME]['etcd']
        if self._is_light:
            self._meta_conf[const.META_SERVICE_CONFIG_NAME]['data_path'] = f'{metasvc_path}'
        else:
            self._meta_conf[const.META_SERVICE_CONFIG_NAME]['data_path'] = f'{metasvc_path}'
            if self.cluster['etcd0'].env.get('ETCD_ENABLE_V2') == 'true':
                etcd_conf['enable'] = 2
            else:
                etcd_conf['enable'] = 1
            etcd_conf['endpoints'] = self.etcd_endpoints

        # 配置cli.conf
        self._cli_conf['chain_id'] = self.chain_id
        self._cli_conf['domain_id'] = self.domain_label
        self._cli_conf['etcd'] = etcd_conf
        if self._is_light:
            self._cli_conf['data_path'] = f'{metasvc_path}'
        else:
            self._cli_conf['data_path'] = f'{metasvc_path}'
        self._cli_conf['mygrid_env_path'] = f'../conf/{const.MYGRID_ENV_JSON_FILENAME}'
        self._cli_conf['mygrid_conf_path'] = f'../conf/{const.MYGRID_CONF_JSON_FILENAME}'

        # 生成相应的docker-compose.yml
        for host, inst_list in self._all_instances.items():
            self._dc_data[host] = {'version': '3.8', 'services': {}}
            dc_services = self._dc_data[host]['services']
            for inst in inst_list:
                image_name = 'pharos_light' if self._is_light else 'pharos'
                docker_image = f'{self._domain.docker.registry}/{image_name}:{self._domain.version}'
                command = f'./pharos -s {inst.service}'
                vols = ['conf', 'data', 'log']
                if inst.service == const.SERVICE_ETCD:
                    docker_image = 'quay.io/coreos/etcd:v3.5.4'
                    command = None
                elif inst.service == const.SERVICE_LIGHT:
                    command = None

                dc_services[inst.name] = {
                    'image': docker_image,
                    'network_mode': 'host',
                    'environment': {**inst.env, 'STORAGE_ETCD': json.dumps(self._cli_conf['etcd'])},
                    'volumes': [{'type': 'bind', 'source': join(inst.dir, v), 'target': f'/pharos/{v}'} for v in vols],
                    'restart': 'always'
                }
                if inst.service == const.SERVICE_ETCD:
                    dc_services[inst.name]['environment']['ETCD_DATA_DIR'] = '/pharos/data/etcd'
                    dc_services[inst.name]['environment']['ETCD_LOG_OUTPUTS'] = '/pharos/log/etcd.log'
                if command:
                    dc_services[inst.name]['command'] = command

    def parse_metrics_config(self):
        global_conf = utils.load_json(self._build_conf('global.conf'))
        metrics_config = global_conf["config"]["metrics"]
        self._domain.common.metrics.enable = metrics_config["enable_pamir_cetina"]
        self._domain.common.metrics.push_address = metrics_config["pamir_cetina_push_address"]
        self._domain.common.metrics.push_port = metrics_config["pamir_cetina_push_port"]
        self._domain.common.metrics.job_name = metrics_config["pamir_cetina_job_name"]
        self._domain.common.metrics.push_interval = metrics_config["pamir_cetina_push_interval"]

    @property
    def is_light(self) -> bool:
        return self._is_light

    @property
    def enable_docker(self) -> bool:
        return self._domain.docker.enable

    @property
    def chain_id(self) -> str:
        return self._domain.chain_id

    @property
    def chain_protocol(self) -> str:
        return self._chain_protocol

    @property
    def domain_label(self) -> str:
        return self._domain.domain_label

    @property
    def deploy_dir(self) -> str:
        return self._domain.deploy_dir

    @property
    def local_client_dir(self) -> str:
        # client dir at localhost depend on chain_id&domain_label
        return f'/tmp/{self.chain_id}/{self.domain_label}/client'

    @property
    def local_dump_dir(self) -> str:
        # dir to dump db data when copy node
        return f'/tmp/{self.chain_id}/dump'

    @property
    def remote_client_dir(self) -> str:
        # client dir at remote is under deploy_dir
        return join(self.deploy_dir, 'client')

    @property
    def run_user(self) -> str:
        return self._domain.run_user

    @property
    def cluster(self) -> Dict[str, Instance]:
        return self._domain.cluster

    @property
    def domain_secret(self) -> SecretFiles:
        return self._domain.secret.domain

    @property
    def client_secret(self) -> SecretFiles:
        return self._domain.secret.client

    @property
    def etcd_endpoints(self) -> List[str]:
        return [f'{node.ip}:{node.port}' for node in self._etcd_cluster]

    @property
    def jsonrpc_endpoint(self) -> str:
        return self._jsonrpc_endpoint

    @property
    def domain_endpoint(self) -> str:
        return f'tcp://{self._domain_ip}:{self._domain_port}'

    def _instances(self, service=None) -> Dict[str, List[Instance]]:
        if not service:
            return self._all_instances
        result = {}
        for host, inst_list in self._all_instances.items():
            inst_list = [
                inst for inst in inst_list if self.cluster[inst.name].service == service]
            if inst_list:
                result[host] = inst_list
        return result

    def _abspath(self, file) -> str:
        return file if isabs(file) else join(self._domain_file_path, file)

    def _build_file(self, *args) -> str:
        return join(self._domain.build_root, *args)

    def _build_binary(self, service) -> str:
        return join(self._domain.build_root, 'bin', const.BINARY_MAP.get(service, service))

    def _build_conf(self, file) -> str:
        return join(self._domain.build_root, 'conf', file)

    def _build_scripts(self, file) -> str:
        return join(self._domain.build_root, 'scripts', file)

    def _instance_bin(self, instance: Instance):
        #  if not self.is_light:
        #  assert instance_name == const.SERVICE_LIGHT 'light mode only has a light instance'
        return const.BINARY_MAP[instance.service]

    def _make_workspace(self, workspace_dir: str, *dir_names: List[str], conn: Connection = None):
        for dir_name in dir_names:
            if conn is None:
                local.run(command.test_mkdir(join(workspace_dir, dir_name)))
            else:
                conn.run(command.test_mkdir(join(workspace_dir, dir_name)))

    def _dump_json(self, file: str, data: Dict[str, Any], conn: Connection = None):
        if conn is None:
            utils.dump_json(file, data)
        else:
            # dump to local temp file, and scp
            temp = NamedTemporaryFile()
            utils.dump_json(temp.name, data)

            # scp local to remote
            conn.put(temp.name, file)

            # delete file
            temp.close()

    '''
	   ___  _
	  / __|| | ___  __ _  _ _
	 | (__ | |/ -_)/ _` || ' \
	  \___||_|\___|\__,_||_||_|

    '''

    def clean_instance(self, instance_name: str, conn: Connection, clean_meta: bool = True):
        # instance_name == 'light' 的时候，根据clean_meta判断是否清理metasvc_db
        logs.info(f'clean {instance_name} on {conn.host}, is clean meta : {clean_meta}')
        instance = self.cluster[instance_name]

        mygrid_placements = extract_mygrid_placements(self._mygrid_env_json)
        metasvc_path = f"{self._mygrid_env_json['mygrid_env']['meta_store_disk']}/{self._mygrid_env_json['mygrid_env']['project_data_path']}"
        logs.info(f'clean {mygrid_placements} {metasvc_path} on {conn.host}')
        for placement in mygrid_placements:
            if clean_meta:
                clean_folder(conn, placement)
            else :
                clean_folder(conn, placement, 'metasvc_db')
        if clean_meta:
            clean_folder(conn, join(instance.dir, 'data'))

        clean_folder(conn, join(instance.dir, 'log'))

        clean_files = [
            join(instance.dir, 'bin/epoch.conf'),
            join(instance.dir, 'bin/*.log'),
            join(instance.dir, 'bin/*.stdout')
        ]
        for file in clean_files:
            conn.run(f'rm -f {file}', warn=True)

    def clean_sqlite(self, instance: Instance, dsn: str, conn: Connection):
        clean_file(conn, join(f'{instance.dir}/bin', dsn))




    def clean_host(self, conn: Connection, service):
        logs.info(f'clean service {service} on {conn.host}')

        for instance in self._instances(service).get(conn.host, []):
            self.clean_instance(instance.name, conn)

    def clean_service(self, service):
        logs.info(f'clean service {service}')

        # clean: 顺序清理, 不并行
        for host in self._instances(service):
            with Connection(host, user=self.run_user) as conn:
                self.clean_host(conn, service)

    def clean(self, service=None, clean_meta: bool = True):
        # clean_all 表示清理包括配置（etcd or metasvc_db）在内的所有数据
        # TODO 暂时未清理client, 需要清理client的storage log
        logs.info(f'clean {self.domain_label}, service: {service}')

        if self.is_light:  # light模式
            light_instance = self.cluster[const.SERVICE_LIGHT]
            with Connection(light_instance.ip, user=self.run_user) as conn:
                self.clean_instance(const.SERVICE_LIGHT, conn, clean_meta)

        elif service is None:  # ultra模式
            # clean 逐个清理每个服务, 默认不清理etcd, clean_all的话，最后清理etcd
            clean_services = const.SERVICES if clean_meta else const.SERVICES[1:]
            for service in clean_services:
                self.clean_service(service)
        else:
            self.clean_service(service)

    '''
	  ___              _
	 |   \  ___  _ __ | | ___  _  _
	 | |) |/ -_)| '_ \| |/ _ \| || |
	 |___/ \___|| .__/|_|\___/ \_, |
	            |_|            |__/
    '''

    def deploy_binary(self, conn: Connection, service=None, backup: bool=False):
        instances = self._instances(service).get(conn.host, [])

        if self.enable_docker:
            # TODO docker-compose.yml是根据domain_file生成的，需要根据domain_file动态变化, 目前只是静态部署
            with tempfile.NamedTemporaryFile(delete=True) as fh:
                fh.write(
                    yaml.dump(self._dc_data[conn.host], sort_keys=False).encode())
                fh.flush()
                conn.sync(fh.name, join(self.deploy_dir, 'docker-compose.yml'))
            time.sleep(2)
            conn.run(f'cd {self.deploy_dir}; docker compose create')
        else:
            # deploy binaries
            deploy_bin_dir = join(self.deploy_dir, 'bin')
            binaries = set()
            for instance in instances:
                binaries.add(self._instance_bin(instance))
            logs.info(f'deploy binaries {binaries} at {deploy_bin_dir}')
            for binary in binaries:
                if backup:
                    conn.run(f'mv {deploy_bin_dir}/{binary} {deploy_bin_dir}/{binary}_bak')
                    conn.run(f'mv {deploy_bin_dir}/{const.PHAROS_VERSION} {deploy_bin_dir}/{const.PHAROS_VERSION}_bak')
                conn.sync(self._build_file('bin', binary), deploy_bin_dir)
                conn.sync(self._build_file('bin', const.PHAROS_VERSION), deploy_bin_dir)
                if self.chain_protocol == const.PROTOCOL_EVM or self.chain_protocol == const.PROTOCOL_ALL:
                    if backup:
                        conn.run(f'mv {deploy_bin_dir}/{const.EVMONE_SO} {deploy_bin_dir}/{const.EVMONE_SO}_bak')
                    conn.sync(self._build_file('bin', const.EVMONE_SO), deploy_bin_dir)

            # link binary
            for instance in instances:
                logs.info(f'deploy {instance.name} at {conn.host}:{instance.dir}')
                self._make_workspace(instance.dir, 'bin', 'conf',
                                 'log', 'data', 'certs', conn=conn)  # instance workspace

                # link binary
                source = join(self.deploy_dir, 'bin', self._instance_bin(instance))
                target = join(instance.dir, 'bin')
                cmd = command.ln_sf_check(source, target)
                if cmd != '':
                    logs.info(cmd)
                    conn.run(cmd)

                # link EVMONE SO
                if self.chain_protocol == const.PROTOCOL_EVM or self.chain_protocol == const.PROTOCOL_ALL:
                    source = join(self.deploy_dir, 'bin', const.EVMONE_SO)
                    target = join(instance.dir, 'bin')
                    cmd = command.ln_sf_check(source, target)
                    if cmd != '':
                        logs.info(cmd)
                        conn.run(cmd)

                # link VERSION
                source = join(self.deploy_dir, 'bin', const.PHAROS_VERSION)
                target = join(instance.dir, 'bin')
                cmd = command.ln_sf_check(source, target)
                if cmd != '':
                    logs.info(cmd)
                    conn.run(cmd)

    def deploy_host_conf(self, conn: Connection, service=None):
        instances = self._instances(service).get(conn.host, [])
           # deploy conf request binaries has been already deployed
        for instance in instances:
            self._cli_conf['mygrid_client_id'] = f'{instance.name}'
            self._cli_conf['service_name'] = f'{instance.service}'
            if self._is_light:
                self._cli_conf['mygrid_client_deploy_mode'] = f'{const.LIGHT_DEPLOY_MODE}'
            else:
                self._cli_conf['mygrid_client_deploy_mode'] = f'{const.ULTRA_DEPLOY_MODE}'

            self._mygrid_client_conf[const.MYGRID_CONFIG_NAME]['mygrid_client_id'] = f'light'

            # generate launch.conf
            if self.cluster[instance.name].service not in [const.SERVICE_ETCD, const.SERVICE_STORAGE]:
                launch_conf_file = join(instance.dir, 'conf/launch.conf')
                launch_conf_data = {
                    'log': {},
                    'parameters': {f'/SetEnv/{k}': v for k, v in instance.env.items()},
                    'init_config': self._cli_conf
                }
                self._dump_json(launch_conf_file, launch_conf_data, conn=conn)

            # generate cubenet.conf and key files(todo)
            if self.cluster[instance.name].service in [const.SERVICE_DOG, const.SERVICE_LIGHT]:
                dog_json_file = utils.load_json(self._build_conf('dog.conf'))
                if dog_json_file['config']['cubenet']['enabled'] == True:
                    cubenet_conf_path = abspath(dog_json_file['config']['cubenet']['config_file']['filepath'])
                    with open(cubenet_conf_path, 'r') as cubenet_conf:
                        cubenet_conf_data = json.load(cubenet_conf)
                    cubenet_conf_data['cubenet']['p2p']['nid'] = self.cluster[instance.name].env["NODE_ID"]
                    port_str = self.cluster[instance.name].env["DOMAIN_LISTEN_URLS0"].split(':')[-1]
                    port_offset = int(dog_json_file['config']['cubenet']['port_offset'])
                    cubenet_conf_data['cubenet']['p2p']['host'][0]['port'] =  str(int(port_str)+ port_offset)
                    cubenet_conf_file = join(instance.dir, 'conf/cubenet.conf')
                    self._dump_json(cubenet_conf_file, cubenet_conf_data, conn=conn)

                    # Only handle cubenet service, write light subsequently uniformly
                    if self.cluster[instance.name].service == const.SERVICE_DOG:
                        key_file = 'generate.key' if self._domain.use_generated_keys else 'new.key'
                        target_key_file = key_file if self._domain.use_generated_keys else 'generate.key'

                        cubenet_certs_dir = join(instance.dir, 'certs/')
                        conn.sync(self._build_file(f'scripts/resources/domain_keys/prime256v1/{self._domain.domain_label}/{key_file}'), join(cubenet_certs_dir, target_key_file))

            # Two sets of key pairs are copied to the deployment path.
            if self.cluster[instance.name].service == const.SERVICE_LIGHT:             
                key_file = 'generate.key' if self._domain.use_generated_keys else 'new.key'
                pkey_file = 'generate.pub' if self._domain.use_generated_keys else 'new.pub'

                deploy_certs_dir = join(instance.dir, 'certs/')

                # 传输时指定目标文件名
                key_files = [
                    (f'scripts/resources/domain_keys/prime256v1/{self._domain.domain_label}/{key_file}', 'generate.key'),
                    (f'scripts/resources/domain_keys/prime256v1/{self._domain.domain_label}/{pkey_file}', 'generate.pub'),
                    (f'scripts/resources/domain_keys/bls12381/{self._domain.domain_label}/{key_file}', 'generate_bls.key'),
                    (f'scripts/resources/domain_keys/bls12381/{self._domain.domain_label}/{pkey_file}', 'generate_bls.pub')
                ]
                
                for src_path, target_name in key_files:
                    src_full_path = self._build_file(src_path)
                    if os.path.exists(src_full_path):
                        conn.sync(src_full_path, join(deploy_certs_dir, target_name))
                        logs.info(f'Synced {target_name} to {conn.host}')
                    else:
                        logs.info(f'Key file {target_name} not found, skipping') 
                                                   
            # generate mygrid config json and mygrid env json
            mygrid_config_json_file = join(instance.dir, f'conf/{const.MYGRID_CONF_JSON_FILENAME}')
            self._dump_json(mygrid_config_json_file, self._mygrid_conf_json, conn=conn)

            mygrid_env_json_file = join(instance.dir, f'conf/{const.MYGRID_ENV_JSON_FILENAME}')
            self._dump_json(mygrid_env_json_file, self._mygrid_env_json, conn=conn)

            # monitor conf
            monitor_json_file = join(instance.dir, f'conf/{const.MONITOR_CONF_JSON_FILENAME}')
            self._dump_json(monitor_json_file, self._monitor_conf_json, conn=conn)

    def deploy_host(self, conn: Connection, service=None, deploy_binary=True, deploy_conf=True):
        instances = self._instances(service).get(conn.host, [])
        logs.info(f'deploy {[inst.name for inst in instances]} at {conn.host}')

        # make pharos root workspace
        self._make_workspace(self.deploy_dir, 'bin', 'conf',
                             conn=conn)  # pharos root workspace

        if deploy_binary:
            self.deploy_binary(conn, service)

        # deploy instances conf
        if deploy_conf:
            self.deploy_host_conf(conn, service)
                
        # 非自适应时，创建meta存放目录
        if not self._domain.mygrid.env.enable_adaptive:
            self._make_workspace(self._mygrid_env_json["mygrid_env"]["meta_store_disk"], self._mygrid_env_json["mygrid_env"]["project_data_path"], conn=conn)


    def deploy_local_cli(self):
        logs.info(f'deploy pharos client at localhost:{self.local_client_dir}')
        # common cli binary for every domain
        # make local client workspace
        self._make_workspace(self.local_client_dir, '../../bin')
        common_cli_bin_dir = join(self.local_client_dir, '../../bin')
        local.sync(self._build_file(
            'bin', const.PHAROS_CLI), common_cli_bin_dir)
        local.sync(self._build_file(
            'bin', const.EVMONE_SO), common_cli_bin_dir)
        local.sync(self._build_file(
            'bin', const.PHAROS_VERSION), common_cli_bin_dir)
        local.sync(self._build_file(
            'bin', const.ETCD_CTL_BIN), common_cli_bin_dir)
        local.sync(self._build_file(
            'bin', const.SVC_META_TOOL), common_cli_bin_dir)

        # def deploy_perf_tools():
        #     try:
        #         local.sync(self._build_file('bin/perf'), common_cli_bin_dir)
        #         local.sync(self._build_file('bin/perf_account_helper.so'), common_cli_bin_dir)
        #         local.sync(self._build_file('bin/perf_ft_helper.so'), common_cli_bin_dir)
        #         local.sync(self._build_file('bin/perf_nft_helper.so'), common_cli_bin_dir)
        #         return True
        #     except Exception as e:
        #         logs.warn(f'failed to deploy perf tools, err = {e}')
        #         return False
        #
        # perf_succ = deploy_perf_tools()

        # local client workspace
        self._make_workspace(self.local_client_dir, 'bin', 'conf')  # make local client workspace
        cli_bin_dir = join(self.local_client_dir, 'bin')
        cli_conf_dir = join(self.local_client_dir, 'conf')
        local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/{const.PHAROS_CLI}')
        local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/{const.EVMONE_SO}')
        local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/{const.PHAROS_VERSION}')
        local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/{const.ETCD_CTL_BIN}')
        local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/{const.SVC_META_TOOL}')

        local.sync(self._build_file('bin', const.PHAROS_CLI), cli_bin_dir, '-avL')
        local.sync(self._build_file('bin', const.EVMONE_SO), cli_bin_dir, '-avL')
        local.sync(self._build_file('bin', const.PHAROS_VERSION), cli_bin_dir)
        local.sync(self._build_file('bin', const.ETCD_CTL_BIN), cli_bin_dir, '-avL')
        local.sync(self._build_file('bin', const.SVC_META_TOOL), cli_bin_dir, '-avL')
        local.sync(self._domain.genesis_conf, cli_conf_dir)

        local.sync(self._build_file(
            'conf', 'resources/poke/node_config.json'), cli_bin_dir)
        key_type = self.client_secret.key_type
        local.sync(self._build_file(
            'conf', f'resources/poke/{key_type}/admin.key'), cli_bin_dir)
        local.sync(self._build_file(
            'conf', f'resources/poke/{key_type}/client'), cli_bin_dir)
        local.sync(self._build_file('conf', 'artifacts'),
                   self.local_client_dir)

        # copy genesis_conf and rename to genesis.conf
        local.sync(self._domain.genesis_conf,
                   join(cli_conf_dir, 'genesis.conf'))

        # if perf_succ:
        #     local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/perf')
        #     local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/perf_account_helper.so')
        #     local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/perf_ft_helper.so')
        #     local.run(f'cd {cli_bin_dir};ln -sf ../../../bin/perf_nft_helper.so')
        #     local.sync(self._build_file('scripts/test/perf.sh'), cli_bin_dir)
        #     local.sync(self._build_file('conf/perf.conf'), cli_bin_dir)

        # 修改node_config.json
        node_conf_file = join(cli_bin_dir, 'node_config.json')
        node_conf = utils.load_json(node_conf_file)
        node_conf['node']['endpoints'] = self._client_endpoints
        utils.dump_json(node_conf_file, node_conf)
        # dump svc.conf 用于pharos_cli
        utils.dump_json(join(cli_bin_dir, const.MYGRID_GENESIS_CONFIG_FILENAME), self._mygrid_client_conf)
        # dump meta_service.conf 用于meta_tool，存储相关子命令
        utils.dump_json(join(cli_bin_dir, const.META_SERVICE_CONFIG_FILENAME), self._meta_conf)
        # dump mygrid.conf.json
        utils.dump_json(join(cli_conf_dir, const.MYGRID_CONF_JSON_FILENAME), self._mygrid_conf_json)
        # dump mygrid.env.json
        utils.dump_json(join(cli_conf_dir, const.MYGRID_ENV_JSON_FILENAME), self._mygrid_env_json)

        # dump cli.conf 用于pharos_cli
        utils.dump_json(join(cli_bin_dir, 'cli.conf'), self._cli_conf)


    def initialize_conf(self, conn: Context):
        # set storage meta data in etcd
        cli_bin_dir = join(self.remote_client_dir, 'bin')

        # set pharos conf in etcd
        logs.info('set pharos conf in etcd')

        json_files = {
            f'/{self.chain_id}/global/config': self._build_conf('global.conf'),
            f'/{self.chain_id}/services/portal/config': self._build_conf('portal.conf'),
            f'/{self.chain_id}/services/dog/config': self._build_conf('dog.conf'),
            f'/{self.chain_id}/services/txpool/config': self._build_conf('txpool.conf'),
            f'/{self.chain_id}/services/controller/config': self._build_conf('controller.conf'),
            f'/{self.chain_id}/services/compute/config': self._build_conf('compute.conf')
        }
        for key, file in json_files.items():
            logs.info(f'set {key}')
            # TODO 使用pharos_cli
            #  conn.run(f'cd {cli_bin_dir}; ./pharos_cli meta -c cli.conf -t cp {file} etcd:/{key}')
            conn.run(
                f"cd {cli_bin_dir}; ./meta_tool -conf {const.META_SERVICE_CONFIG_FILENAME} -set -key={key} -value='{load_file(file)}'")
        confs = {
            f'/{self.chain_id}/portal/certs': {
                'ca.crt': f'{to_base64(self.client_secret.files["ca_cert"])}',
                'server.crt': f'{to_base64(self.client_secret.files["cert"])}',
                'server.key': f'{to_base64(self.client_secret.files["key"])}',
            },
            f'/{self.chain_id}/secrets/domain.key': {
                'domain_key': f'{to_base64(self.domain_secret.files["key"])}',
                'stabilizing_key': f'{to_base64(self.domain_secret.files["stabilizing_key"])}',
            }
        }
        for name, instance in self.cluster.items():
            if instance.log or instance.config:
                confs[f'/{self.chain_id}/services/{instance.service}/instance_config/{name}'] = {
                    'log': instance.log,
                    'parameters': {f'/GlobalFlag/{k}': v for k, v in instance.gflags.items()},
                    'config': instance.config,
                }
        for key, value in confs.items():
            logs.info(f'set {key}')
            # TODO 使用pharos_cli
            conn.run(
                f"cd {cli_bin_dir}; ./meta_tool -conf {const.META_SERVICE_CONFIG_FILENAME} -set -key={key} -value='{json.dumps(value)}'")
        # TODO 保存domain files到etcd

    def deploy(self, service=None):
        logs.info(f'deploy {self.domain_label}, service: {service}')
        # clean data and log
        self.clean(service, clean_meta=True)

        # concurrent deploy at multiple host
        with ConcurrentGroup(*self._instances(service).keys(), user=self.run_user) as group:
            group.call(self.deploy_host, service)

        deploy_client_host = None
        if self.is_light or service == const.SERVICE_LIGHT:
            deploy_client_host = self.cluster[const.SERVICE_LIGHT].ip
        elif service is None:
            # 默认部署client到controller所在远程host
            deploy_client_host = self.cluster[const.SERVICE_CONTROLLER].ip

        if deploy_client_host is not None:
            # deploy pharos client at local host and controller(light) host
            self.deploy_local_cli()
            if not is_local(deploy_client_host) or self.local_client_dir != self.remote_client_dir:
                with Connection(deploy_client_host, user=self.run_user) as conn:
                    # storage env.json的bin_dir指向build root, 所以部署到远程后bin_dir是无效的,
                    # 但是远程只执行svc_setmeta, 不依赖bin_dir
                    # 本地client目录同步至远程，copy softlink binary
                    conn.sync(self.local_client_dir,
                              self.deploy_dir, rsync_opts='-avzL')

            ## initialize conf in config center(etcd or rocksdb)
            # try:
            #     if not self.is_light:
            #         logs.info('start etcd')
            #         self.start_service(const.SERVICE_ETCD)
            #     with Connection(deploy_client_host, user=self.run_user) as conn:
            #         self.initialize_conf(conn)
            # except Exception as e:
            #     logs.error('{}'.format(e))
            # finally:
            #     if not self.is_light:
            #         logs.info('stop etcd')
            #         self.stop_service(const.SERVICE_ETCD)

    def sync_cli_bin(self, local_client_dir: str, deploy_client_host, remote_client_dir):
        with Connection(deploy_client_host, user=self.run_user) as conn:
            bin_includes = " ".join(f"--include='**/{item}'" for item in const.CLI_BINARYS)
            sync_opts = f'-avzL --ignore-existing --include="*/" {bin_includes} --exclude="*"'

            conn.sync(self.local_client_dir, self.deploy_dir,  rsync_opts=sync_opts)

    def sync_cli_conf(self, local_client_dir: str, deploy_client_host, remote_client_dir):        
        with Connection(deploy_client_host, user=self.run_user) as conn:
            includes = [
                "--include=conf/",        
                "--include=conf/**",      
                "--include=bin/",         
                "--include=bin/*.conf",
                "--include=bin/*.json",
                "--exclude=*"
            ]
            
            sync_opts = f'-avzL {" ".join(includes)}'
            
            source_path = self.local_client_dir.rstrip('/') + '/'
            target_path = f"{self.deploy_dir}/client/"
            
            logs.info(f'update client conf: {source_path} -> {deploy_client_host}:{target_path}')  
            conn.sync(source_path, target_path, rsync_opts=sync_opts)   

    def update(self, service=None):
        logs.info(f'update {self.domain_label}, service: {service}')

        # concurrent deploy multible binary
        with ConcurrentGroup(*self._instances(service).keys(), user=self.run_user) as group:
            group.call(self.deploy_binary, service)

        # deploy client tool
        deploy_client_host = None
        if self.is_light or service == const.SERVICE_LIGHT:
            deploy_client_host = self.cluster[const.SERVICE_LIGHT].ip
        elif service is None:
            # 默认部署client到controller所在远程host
            deploy_client_host = self.cluster[const.SERVICE_CONTROLLER].ip

        if deploy_client_host is not None:
            # deploy pharos client at local host and controller(light) host
            self.deploy_local_cli()
            if not is_local(deploy_client_host) or self.local_client_dir != self.remote_client_dir:
                with Connection(deploy_client_host, user=self.run_user) as conn:
                    # storage env.json的bin_dir指向build root, 所以部署到远程后bin_dir是无效的,
                    # 但是远程只执行svc_setmeta, 不依赖bin_dir
                    # 本地client目录同步至远程，copy softlink binary
                    self.sync_cli_bin(self.local_client_dir, deploy_client_host, self.deploy_dir)

    def update_conf(self, service=None):

        logs.info(f'update conf {self.domain_label}, service: {service}')
        # concurrent deploy multible conf
        with ConcurrentGroup(*self._instances(service).keys(), user=self.run_user) as group:
            group.call(self.deploy_host_conf, service)

        # deploy client conf
        deploy_client_host = None
        if self.is_light or service == const.SERVICE_LIGHT:
            deploy_client_host = self.cluster[const.SERVICE_LIGHT].ip
        elif service is None:
            # 默认部署client到controller所在远程host
            deploy_client_host = self.cluster[const.SERVICE_CONTROLLER].ip

        if deploy_client_host is not None:
            # deploy pharos client at local host and controller(light) host
            self.deploy_local_cli()
            if not is_local(deploy_client_host) or self.local_client_dir != self.remote_client_dir:
                with Connection(deploy_client_host, user=self.run_user) as conn:
                    # storage env.json的bin_dir指向build root, 所以部署到远程后bin_dir是无效的,
                    # 但是远程只执行svc_setmeta, 不依赖bin_dir
                    # 本地client目录同步至远程，copy softlink binary
                    self.sync_cli_conf(self.local_client_dir, deploy_client_host, self.deploy_dir)

        # write conf to storage
        if self.is_light:
            with Connection(self.cluster[const.SERVICE_LIGHT].ip, user=self.run_user) as conn:
                # write meta
                self.initialize_conf(conn)
        else:
            self.start_service(const.SERVICE_ETCD)
            self.start_service(const.SERVICE_STORAGE)
            try:
                with Connection(self.cluster[const.SERVICE_CONTROLLER].ip, user=self.run_user) as conn:
                    # write meta
                    self.initialize_conf(conn)
            except Exception as e:
                logs.error('{}'.format(e))
            finally:
                self.stop_service(const.SERVICE_STORAGE)
                self.stop_service(const.SERVICE_ETCD)

    def clone_from(self, is_cold) ->  Dict[str, List[str]]:
        if not self.is_light:
            logs.error('Domain clone only support light mode for now')
            return
        (src_placements_map, project_data_path) = (
            extract_mygrid_placements_with_key(self._mygrid_env_json)
        )
        if is_cold:
            # stop domain
            self.stop()

            placements_set = set()
            for (key, paths) in src_placements_map.items():
                for item in paths:
                    placements_set.add((item, f'{item}/{project_data_path}/public/'))

        else:
            # make snapshot
            snapshot_name = f'ops_clone_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            light_instance = self.cluster[const.SERVICE_LIGHT]

            with Connection(light_instance.ip, user=self.run_user) as conn:
                cli_bin_dir = join(self.remote_client_dir, 'bin')
                ret = conn.run(f'cd {cli_bin_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./pharos_cli snapshot -d {snapshot_name}')
                if not ret.ok:
                    logs.error(f'snap shot error: {ret.stderr}')

            placements_set = set()
            for (key, paths) in src_placements_map.items():
                for item in paths:
                    placements_set.add((item, f'{item}/{project_data_path}/snapshot/{snapshot_name}/'))


        logs.debug("clone prepare, placements: {placements_set}")

        # copy db to ag
        light_instance = self.cluster[const.SERVICE_LIGHT]
        with Connection(light_instance.ip, user=self.run_user) as conn:
            for (placement, path) in placements_set:
                target_dir = self.local_dump_dir + placement + '/public'
                local.run(command.test_mkdir(target_dir))
                local.clean_folder(target_dir)

                conn.sync_back(path, target_dir)

        if is_cold:
            #restart domain
            self.start()
        else:
            with Connection(light_instance.ip, user=self.run_user) as conn:
                for (_, snapshot_path) in placements_set:
                    clean_folder(conn, snapshot_path)


        return (src_placements_map, project_data_path)

    def clone_to(self, src_placement: Tuple[Dict[str, List[str]], str], backup: bool):
        if not self.is_light:
            logs.error('Domain clone only support light mode for now')
            return
        # stop target domain
        self.stop()

        # collect target domain placement
        (dst_placements, dst_project_data_path) = (
            extract_mygrid_placements_with_key(self._mygrid_env_json)
        )
        (src_placements, src_project_data_path) = src_placement

        placement_map = (
            generate_interdomain_placements_map(src_placements, dst_placements)
        )

        light_instance = self.cluster[const.SERVICE_LIGHT]
        with Connection(light_instance.ip, user=self.run_user) as conn:
            if backup:
                # backup db
                for _, dst_placement in placement_map.items():
                    dst_db_path = f'{dst_placement}/{dst_project_data_path}/public'
                    backup_command = f'mv {dst_db_path} {dst_db_path}_bak'

                    result = conn.run(backup_command, warn=True)
                    if result.failed and (not result.stderr.endswith('No such file or directory')):
                        logs.error(f'backup db failed: {result}')
                        return

            # copy db_path to target domain
            for src_placement, dst_placement in placement_map.items():
                src_db_path = f'{self.local_dump_dir}{src_placement}/public'
                dst_db_path = join(dst_placement, dst_project_data_path)

                conn.sync(src_db_path, dst_db_path, rsync_opts='-av --delete')

    STAKING_ABI = '''
[
  {
    "inputs": [],
    "stateMutability": "nonpayable",
    "type": "constructor"
  },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "description",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "publicKey",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "blsPublicKey",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "string",
        "name": "endpoint",
        "type": "string"
      },
      {
        "indexed": false,
        "internalType": "uint64",
        "name": "effectiveBlockNum",
        "type": "uint64"
      },
      {
        "indexed": false,
        "internalType": "uint8",
        "name": "status",
        "type": "uint8"
      }
    ],
    "name": "DomainUpdate",
    "type": "event"
  },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "uint256",
        "name": "epochNumber",
        "type": "uint256"
      },
      {
        "indexed": true,
        "internalType": "uint256",
        "name": "blockNumber",
        "type": "uint256"
      },
      {
        "indexed": false,
        "internalType": "uint256",
        "name": "timestamp",
        "type": "uint256"
      },
      {
        "indexed": false,
        "internalType": "uint256",
        "name": "totalStake",
        "type": "uint256"
      },
      {
        "indexed": false,
        "internalType": "bytes32[]",
        "name": "activeValidators",
        "type": "bytes32[]"
      }
    ],
    "name": "EpochChange",
    "type": "event"
  },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "address",
        "name": "delegator",
        "type": "address"
      },
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      },
      {
        "indexed": false,
        "internalType": "uint256",
        "name": "amount",
        "type": "uint256"
      }
    ],
    "name": "StakeAdded",
    "type": "event"
  },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      }
    ],
    "name": "ValidatorExitRequested",
    "type": "event"
  },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "address",
        "name": "validator",
        "type": "address"
      },
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      }
    ],
    "name": "ValidatorRegistered",
    "type": "event"
   },
  {
    "anonymous": false,
    "inputs": [
      {
        "indexed": true,
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      }
    ],
    "name": "ValidatorUpdated",
    "type": "event"
  },
  {
    "inputs": [],
    "name": "EPOCH_DURATION",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "MAX_POOL_STAKE",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "MIN_DELEGATOR_STAKE",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "MIN_POOL_STAKE",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "MIN_VALIDATOR_STAKE",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "name": "activePoolIds",
    "outputs": [
      {
        "internalType": "bytes32",
        "name": "",
        "type": "bytes32"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      }
    ],
    "name": "addStake",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "advanceEpoch",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "currentEpoch",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      }
    ],
    "name": "exitValidator",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "getActiveValidators",
    "outputs": [
      {
        "internalType": "bytes32[]",
        "name": "",
        "type": "bytes32[]"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      }
    ],
    "name": "getValidatorInfo",
    "outputs": [
      {
        "components": [
          {
            "internalType": "string",
            "name": "description",
            "type": "string"
          },
          {
            "internalType": "string",
            "name": "publicKey",
            "type": "string"
          },
          {
            "internalType": "string",
            "name": "publicKeyPop",
            "type": "string"
          },
          {
            "internalType": "string",
            "name": "blsPublicKey",
            "type": "string"
          },
          {
            "internalType": "string",
            "name": "blsPublicKeyPop",
            "type": "string"
          },
          {
            "internalType": "string",
            "name": "endpoint",
            "type": "string"
          },
          {
            "internalType": "uint8",
            "name": "status",
            "type": "uint8"
          },
          {
            "internalType": "bytes32",
            "name": "poolId",
            "type": "bytes32"
          },
          {
            "internalType": "uint256",
            "name": "totalStake",
            "type": "uint256"
          }
        ],
        "internalType": "struct DPoSValidatorManager.Validator",
        "name": "",
        "type": "tuple"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "string",
        "name": "str",
        "type": "string"
      }
    ],
    "name": "hexStringToBytes",
    "outputs": [
      {
        "internalType": "bytes",
        "name": "",
        "type": "bytes"
      }
    ],
    "stateMutability": "pure",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "name": "pendingAddPoolIds",
    "outputs": [
      {
        "internalType": "bytes32",
        "name": "",
        "type": "bytes32"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "name": "pendingExitPoolIds",
    "outputs": [
      {
        "internalType": "bytes32",
        "name": "",
        "type": "bytes32"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "string",
        "name": "_description",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_publicKey",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_publicKeyPop",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_blsPublicKey",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_blsPublicKeyPop",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_endpoint",
        "type": "string"
      }
    ],
    "name": "registerValidator",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      }
    ],
    "name": "slashValidator",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "totalStake",
    "outputs": [
      {
        "internalType": "uint256",
        "name": "",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      },
      {
        "internalType": "string",
        "name": "_description",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "_endpoint",
        "type": "string"
      },
      {
        "internalType": "address",
        "name": "_new_owner",
        "type": "address"
      }
    ],
    "name": "updateValidator",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "",
        "type": "bytes32"
      }
    ],
    "name": "validators",
    "outputs": [
      {
        "internalType": "string",
        "name": "description",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "publicKey",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "publicKeyPop",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "blsPublicKey",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "blsPublicKeyPop",
        "type": "string"
      },
      {
        "internalType": "string",
        "name": "endpoint",
        "type": "string"
      },
      {
        "internalType": "uint8",
        "name": "status",
        "type": "uint8"
      },
      {
        "internalType": "bytes32",
        "name": "poolId",
        "type": "bytes32"
      },
      {
        "internalType": "uint256",
        "name": "totalStake",
        "type": "uint256"
      }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      {
        "internalType": "bytes32",
        "name": "_poolId",
        "type": "bytes32"
      }
    ],
    "name": "withdrawRewards",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]
    '''
    STAKING_ADDRESS = '0x4100000000000000000000000000000000000000'

    def update_validator(self, endpoint: str, key: str, poolId: str, new_owner: str):
        if len(poolId)!=64:
            logs.fatal(f"poolId must be 64 , but got {len(poolId)}")
        poolIdBytes = bytes(HexBytes(poolId))
        parameters = [
            poolIdBytes,
            self.domain_label,
            self.domain_endpoint,
            Web3().to_checksum_address(new_owner),
        ]
        web3 = Web3(Web3.HTTPProvider(endpoint))
        if web3.is_connected():
            logs.info("web3 is connected")
        else:
            logs.error("web3 is not connected")
        account = Account.from_key(key)
        staking_contract = web3.eth.contract(
            address=Composer.STAKING_ADDRESS, abi=Composer.STAKING_ABI
        )
        tx = staking_contract.functions.updateValidator(*parameters).buildTransaction(
            {
                "value": 0,
                "from": account.address,
                "nonce": web3.eth.getTransactionCount(account.address),
                "gasPrice": 1,
            }
        )
        print("end tx")
        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
        receipt = web3.eth.waitForTransactionReceipt(tx_hash)
        if receipt["status"] == 1:
            logs.info("validator update success")
        else:
            logs.error("validator update failed")

        logs.info(f"validator update tx: {tx_hash.hex()}")
        logs.info(f"validator update receipt: {receipt}")  


    def add_validator(self, endpoint: str, key: str):
        try:
            with open(self.domain_secret.files.get('key_pub', "r")) as pk_file:
                domain_pubkey = pk_file.readline().strip()
        except Exception as e:
            domain_pubkey, _ = Generator._get_pubkey(self.domain_secret.key_type, self.domain_secret.files.get('key'))

        stabilizing_pk_file = self.domain_secret.files.get('stabilizing_pk')

        domain_pubkey = '0x' + domain_pubkey

        with open(stabilizing_pk_file, 'r') as spk_file:
            spk = spk_file.read().strip()

        parameters = [self.domain_label, domain_pubkey,"0x00", spk, "0x00", self.domain_endpoint]

        web3 = Web3(Web3.HTTPProvider(endpoint))
        if web3.is_connected():
            logs.info('web3 is connected')
        else:
            logs.error('web3 is not connected')

        account = Account.from_key(key)

        staking_contract = web3.eth.contract(address=Composer.STAKING_ADDRESS, abi=Composer.STAKING_ABI)
        tx = staking_contract.functions.registerValidator(*parameters).buildTransaction({
            'value': 1000000000000000000,
            'from': account.address,
            'nonce': web3.eth.getTransactionCount(account.address),
            'gasPrice': 1000000000
        })

        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)

        receipt = web3.eth.waitForTransactionReceipt(tx_hash)
        if receipt['status'] == 1:
            logs.info('validator register success')
        else:
            logs.error('validator register failed')

        logs.info(f'validator register tx: {tx_hash.hex()}')
        logs.info(f'validator register receipt: {receipt}')



    def exit_validator(self,endpoint: str, key: str):
        try:
            with open(self.domain_secret.files.get('key_pub', "r")) as pk_file:
                domain_pubkey = pk_file.readline().strip()
                domain_pubkey_bytes = bytes.fromhex(f'{domain_pubkey}')
        except Exception as e:
            _, domain_pubkey_bytes = Generator._get_pubkey(self.domain_secret.key_type, self.domain_secret.files.get('key'))

        web3 = Web3(Web3.HTTPProvider(endpoint))

        poolid = hashlib.sha256(bytes(domain_pubkey_bytes)).digest()

        logs.info(f"poolid: {poolid.hex()}")

        logs.info(f'domain id: {poolid}')

        parameters = [poolid]

        account = Account.from_key(key)

        if web3.is_connected():
            logs.info('web3 is connected')
        else:
            logs.error('web3 is not connected')

        staking_contract = web3.eth.contract(address=Composer.STAKING_ADDRESS, abi=Composer.STAKING_ABI)
        tx = staking_contract.functions.exitValidator(*parameters).buildTransaction({
            'value': 0,
            'from': account.address,
            'nonce': web3.eth.getTransactionCount(account.address),
            'gas': 2000000,  # 默认 gas limit
            'gasPrice': 1000000000
        })

        signed_tx = web3.eth.account.sign_transaction(tx, key)
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)

        receipt = web3.eth.waitForTransactionReceipt(tx_hash)

        if receipt['status'] == 1:
            logs.info('validator exit success')
        else:
            logs.error('validator exit failed')

        logs.info(f'validator exit tx: {tx_hash.hex()}')
        logs.info(f'validator exit receipt: {receipt}')

    '''
	  ___  _          _
	 / __|| |_  __ _ | |_  _  _  ___
	 \__ \|  _|/ _` ||  _|| || |(_-<
	 |___/ \__|\__,_| \__| \_,_|/__/

    '''

    def status_host(self, conn: Connection, service=None):
        if self.enable_docker:
            # TODO filter service
            logs.info(conn.host)
            if service:
                conn.run(
                    f'cd {self.deploy_dir}; docker compose ps -a |grep {service}', warn=True)
            else:
                conn.run(
                    f'cd {self.deploy_dir}; docker compose ps -a', warn=True)
            return

        services = set()
        for instance in self._instances(service).get(conn.host, []):
            services.add(instance.service)

        result = []
        cmd = f"ps -eo pid,user,cmd |grep -E '{'|'.join(services)}'| grep -v grep|grep -v watchdog"
        ret = conn.run(cmd, warn=True, hide=True)
        for line in ret.stdout.splitlines():
            out = line.split(maxsplit=2)
            ret = conn.run(f'pwdx {out[0]}', warn=True, hide=True)
            if not ret.ok:
                continue
            work_dir = ret.stdout.strip().split(':')[-1]
            if self.deploy_dir in work_dir:
                out.insert(2, work_dir)
                out_str = f'{conn.host :<15}{out[0] :<8}{out[1] :<12}{out[2] :<48}{out[3]}'
                result.append(out_str)
                #  result.append('\t'.join([f'{conn.host}:'] + out))
        logs.echo('\n'.join(result))
        return ret.exited

    def status(self, service):
        if service:
            logs.info(f'==========={self.domain_label} {service}==========')
        else:
            logs.info(f'==========={self.domain_label}===========')
        for host in self._instances(service):
            with Connection(host, user=self.run_user) as conn:
                self.status_host(conn, service)

    '''
	  ___  _
	 / __|| |_  ___  _ __
	 \__ \|  _|/ _ \| '_ \
	 |___/ \__|\___/| .__/
	                |_|
    '''

    def stop_instance(self, instance: Instance, conn: Connection):
        logs.info(f'stop {instance.name} on {conn.host}')

        if self.enable_docker:
            conn.run(
                f'cd {self.deploy_dir}; docker compose stop {instance.name}', warn=True)
        else:
            work_dir = join(instance.dir, 'bin')
            binary = self._instance_bin(instance)
            # TODO use --stop to stop pharos service
            # cmd = f'cd {bin_dir}; ./{bin_name} -s {self.cluster[instance_name].service} --stop'
            cmd = command.pspid_greps(binary, "awk '{system(\"pwdx \"$1\" 2>&1\")}'", 'grep -v MATCH_MATCH',
                                      'sed "s#{}#MATCH_MATCH#g"'.format(
                                          work_dir), 'grep MATCH_MATCH',
                                      "awk -F: '{system(\"kill -9 \"$1\" 2>&1\")}'")
            conn.run(cmd)

    def graceful_stop_instance(self, instance: Instance, conn: Connection):
        logs.info(f'stop {instance.name} on {conn.host}')

        if self.enable_docker:
            conn.run(
                f'cd {self.deploy_dir}; docker compose stop {instance.name}', warn=True)
        else:
            work_dir = join(instance.dir, 'bin')
            binary = self._instance_bin(instance)
            # TODO use --stop to stop pharos service
            # cmd = f'cd {bin_dir}; ./{bin_name} -s {self.cluster[instance_name].service} --stop'
            cmd = command.pspid_greps(binary, "awk '{system(\"pwdx \"$1\" 2>&1\")}'", 'grep -v MATCH_MATCH',
                                      'sed "s#{}#MATCH_MATCH#g"'.format(
                                          work_dir), 'grep MATCH_MATCH',
                                      "awk -F: '{system(\"kill -15 \"$1\" 2>&1\")}'")
            conn.run(cmd)

    def stop_host(self, conn: Connection, service, force=False):
        logs.info(f'stop service {service} on {conn.host}, force {force}')

        if self.enable_docker and not service:
            conn.run(f'cd {self.deploy_dir}; docker compose stop', warn=True)
        else:
            if force == False:
                for instance in self._instances(service).get(conn.host, []):
                    self.graceful_stop_instance(instance, conn)
                timeout = 5
                while self.status_host(conn, service) == 0:
                    if timeout <= 0:
                        for instance in self._instances(service).get(conn.host, []):
                            self.stop_instance(instance, conn)
                        logs.info(
                            f'stop service {service} on {conn.host} immediately')
                        break
                    timeout -= 1
                    logs.debug(
                        f'stop service {service} on {conn.host} will sleep 1s')
                    time.sleep(1)
                else:
                    logs.info(f'stop service {service} on {conn.host} gracefully')
            else:
                # force stop
                for instance in self._instances(service).get(conn.host, []):
                    self.stop_instance(instance, conn)
                logs.info(
                    f'stop service {service} on {conn.host} immediately')
            
    def stop_service(self, service, force=False):
        logs.info(f'stop service {service} force {force}')

        # stop: 顺序停止, 不并行
        for host in self._instances(service):
            with Connection(host, user=self.run_user) as conn:
                self.stop_host(conn, service, force)

    def stop(self, service=None, force=False):
        logs.info(f'stop {self.domain_label}, service: {service}, force: {force}')

        if self.enable_docker and not service:
            self.stop_service(None, force)
            self.status(None)
            return

        if self.is_light:  # light模式
            if service not in [None, 'light']:
                logs.error('light mode only has light instance')
                return
            self.stop_service(const.SERVICE_LIGHT, force)
        elif service is None:  # ultra模式
            # stop 逐个停止每个服务
            for s in reversed(const.SERVICES):
                self.stop_service(s, force)
        else:
            self.stop_service(service, force)
        self.status(service)

    """
	  ___  _               _
	 / __|| |_  __ _  _ _ | |_
	 \__ \|  _|/ _` || '_||  _|
	 |___/ \__|\__,_||_|   \__|
    """

    def start_instance(self, instance: Instance, conn: Connection):
        logs.info(f'start {instance} on {conn.host}')

        if self._domain.enable_setkey_env:
            # 准备环境变量前缀
            env_prefix = f"export CONSENSUS_KEY_PWD='{self._domain.key_passwd}'; export PORTAL_SSL_PWD='{self._domain.portal_ssl_pass}';"
            logs.info(f'Setting environment variables at {conn.host}')            
        else:
            # enable_setkey_env关闭时，需手动设置环境变量
            # 检查多个环境变量
            env_vars_to_check = ['CONSENSUS_KEY_PWD', 'PORTAL_SSL_PWD']

            for env_var in env_vars_to_check:
                check_env_result = conn.run(f"[ -n \"${env_var}\" ]", warn=True)
                if not check_env_result.ok:
                    raise Exception(f"{env_var} environment variable not set at {conn.host}. Please set it manually.")
                logs.info(f'Environment variable {env_var} verified at {conn.host}')
    
        if self.enable_docker:
            conn.run(
                f'cd {self.deploy_dir}; docker compose start {instance.name}')
        else:
            work_dir = join(instance.dir, 'bin')
            binary = self._instance_bin(instance)
            if exists(conn, join(instance.dir, 'conf/launch.conf')):
                if self.is_light:
                    if self.chain_protocol == const.PROTOCOL_EVM or self.chain_protocol == const.PROTOCOL_ALL:
                        cmd = f"cd {work_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./{binary} -c ../conf/launch.conf -d"
                    else:
                        cmd = f"cd {work_dir}; ./{binary} -c ../conf/launch.conf -d"
                else:
                    if self.chain_protocol == const.PROTOCOL_EVM or self.chain_protocol == const.PROTOCOL_ALL:
                        cmd = f"cd {work_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./{binary} -c ../conf/launch.conf -s {instance.service} -d"
                    else:
                        cmd = f"cd {work_dir}; ./{binary} -c ../conf/launch.conf -s {instance.service} -d"
                conn.run(f"{env_prefix}{cmd}")

            elif instance.service == const.SERVICE_ETCD:
                cmds = []
                for k, v in instance.env.items():
                    cmds.append(command.export(k, v))
                # FIXME 临时把etcd信息整个作为一个环境变量
                cmds.append(command.export('STORAGE_ETCD',
                            json.dumps(self._cli_conf['etcd'])))
                # TODO: docker-compose 暂不支持start命令行指定的存储额外命令行参数
                # 目前docker-compose.yml只在deploy的时候创建并执行docker compose create
                # 需要在start的时候更新docker-compose.yml, 并重新docker compose create
                cmd = f"cd {work_dir}; ./{binary} {' '.join(instance.args)}"
                time.sleep(3)
                logs.info(f'{conn.host}: {cmd}')
                cmds.append(cmd)
                conn.run(f"{env_prefix}{';'.join(cmds)}")

            elif instance.service == const.SERVICE_STORAGE:
                cmds = []
                # TODO: docker-compose 暂不支持start命令行指定的存储额外命令行参数
                # 目前docker-compose.yml只在deploy的时候创建并执行docker compose create
                # 需要在start的时候更新docker-compose.yml, 并重新docker compose create
                cmd = ""
                cmd += f"cd {work_dir}; ./{binary} --role=master --conf=../conf/{const.MYGRID_CONF_JSON_FILENAME} --env=../conf/{const.MYGRID_ENV_JSON_FILENAME} > master.log 2>&1 &"
                cmd += f"sleep 3 &"
                cmd += f"cd {work_dir}; ./{binary} --role=server --server_id=0 --conf=../conf/{const.MYGRID_CONF_JSON_FILENAME} --env=../conf/{const.MYGRID_ENV_JSON_FILENAME} > server.log 2>&1 &"
                logs.info(f'{conn.host}: {cmd}')
                cmds.append(cmd)
                conn.run(f"{env_prefix}{';'.join(cmds)}")
                time.sleep(3)

    def start_host(self, conn: Connection, service):
        logs.info(f'start service {service} on {conn.host}')

        if self.enable_docker and not service:
            conn.run(f'cd {self.deploy_dir}; docker compose start')
        else:
            for instance in self._instances(service).get(conn.host, []):
                self.start_instance(instance, conn)

    def start_service(self, service):
        logs.info(f'start service {service}')

        # start: 顺序启动, 不并行
        for host in self._instances(service):
            with Connection(host, user=self.run_user) as conn:
                self.start_host(conn, service)

    def start(self, service=None, extra_storage_args: str = ''):
        logs.info(f'start {self.domain_label}, service: {service}')

        # 方便性能测试场景，方便的注入存储命令行参数，只有start的时候使用
        self._extra_storage_start_args = extra_storage_args
        if self.enable_docker and not service:
            self.start_service(None)
            self.status(None)
            return
        if self.is_light:  # light模式
            if service not in [None, 'light']:
                logs.error('light mode only has light instance')
                return
            self.start_service(const.SERVICE_LIGHT)
        elif service is None:  # ultra模式
            # start 逐个启动每个服务, etcd是第一个启动的服务
            for s in const.SERVICES:
                self.start_service(s)
        else:
            self.start_service(service)
        self.status(service)

    '''
	  ___            _        _
	 | _ ) ___  ___ | |_  ___| |_  _ _  __ _  _ __
	 | _ \/ _ \/ _ \|  _|(_-<|  _|| '_|/ _` || '_ \
	 |___/\___/\___/ \__|/__/ \__||_|  \__,_|| .__/
	                                         |_|
    '''

    def bootstrap(self):
        logs.info('bootstrap')

        if self.is_light:
            # clean all logs and data except metasvc_db
            self.clean(const.SERVICE_LIGHT)
            logs.info('start generate genesis state')
            try:
                with Connection(self.cluster[const.SERVICE_LIGHT].ip, user=self.run_user) as conn:
                    # write meta
                    self.initialize_conf(conn)

                    # genesis
                    cli_bin_dir = join(self.remote_client_dir, 'bin')
                    cmd = f'cd {cli_bin_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./pharos_cli genesis -g ../conf/genesis.conf --spec 0 -s {const.MYGRID_GENESIS_CONFIG_FILENAME}'
                    logs.info(f'{conn.host}: {cmd}')
                    conn.run(cmd)
            except Exception as e:
                logs.error('{}'.format(e))
        else:
            # clean all data
            self.clean(None)
            self.start_service(const.SERVICE_ETCD)
            self.start_service(const.SERVICE_STORAGE)
            logs.info('start generate genesis state')
            try:
                with Connection(self.cluster[const.SERVICE_CONTROLLER].ip, user=self.run_user) as conn:
                    # write meta
                    self.initialize_conf(conn)

                    # genesis
                    cli_bin_dir = join(self.remote_client_dir, 'bin')
                    cmd = f'cd {cli_bin_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./pharos_cli genesis -g ../conf/genesis.conf --spec 0 -s {const.MYGRID_GENESIS_CONFIG_FILENAME}'
                    logs.info(f'{conn.host}: {cmd}')
                    conn.run(cmd)
            except Exception as e:
                logs.error('{}'.format(e))
            finally:
                self.stop_service(const.SERVICE_STORAGE)
                self.stop_service(const.SERVICE_ETCD)

    def cli_dbquery(self, query_arg: str):
        try:
            light_instance = self.cluster[const.SERVICE_LIGHT]
            with Connection(light_instance.ip, user=self.run_user) as conn:
                result = conn.run('mktemp', hide=True)
                if result.failed:
                    logs.error(f'Failed to create temp file on remote: {result.stderr}')
                    return None

                # create remote dbquery output file
                remote_temp_file = result.stdout.strip()
                try:
                    cli_bin_dir = join(self.remote_client_dir, 'bin')
                    command = f'cd {cli_bin_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./pharos_cli dbquery {query_arg} -o {remote_temp_file}; cat {remote_temp_file}'
                    result = conn.run(command, hide=True)
                    if result.failed:
                        logs.error(f'Failed to execute dbquery on remote: {result.stderr}')
                        return None

                    local_temp_file = tempfile.NamedTemporaryFile()
                    conn.get(remote_temp_file, local_temp_file.name)

                    result = local_temp_file.read().decode('utf-8')
                    if len(result) == 0:
                        return None

                    # Return json object if result is json string, return raw string otherwise
                    try:
                        return json.loads(result)
                    except (ValueError, TypeError):
                        return result

                finally:
                    # delete remote temp file
                    # conn.run(f'rm {remote_temp_file}')
                    pass

        except Exception as e:
            logs.error(f'Exception when execute dbquery: {e}')
            return None

    def jrpc_query(self, method_name: str, params):
        payload = {
            "jsonrpc": "2.0",
            "method": method_name,
            "params": params,
            "id": random.randint(1, 65535)
        }
        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.jsonrpc_endpoint, json=payload, headers=headers)
        except Exception as e:
            logs.warn(f'Execute jrpc query failed: {e}')
            return None

        result = response.json()
        if "result" in result:
            return result["result"]
        else:
            logs.error(f'Result not found in response: {result}')
            return None

    def cli_dumpstate(self, arg: str):
        try:
            light_instance = self.cluster[const.SERVICE_LIGHT]
            with Connection(light_instance.ip, user=self.run_user) as conn:
                result = conn.run('mktemp', hide=True)
                if result.failed:
                    logs.error(f'Failed to create temp file on remote: {result.stderr}')
                    return None

                # create remote dbquery output file
                remote_temp_file = result.stdout.strip()
                try:
                    cli_bin_dir = join(self.remote_client_dir, 'bin')
                    command = f'cd {cli_bin_dir}; LD_PRELOAD=./{const.EVMONE_SO} ./pharos_cli dumpstate {arg} -o {remote_temp_file}; cat {remote_temp_file}'
                    result = conn.run(command, hide=True)
                    if result.failed:
                        logs.error(f'Failed to execute dumpstate on remote: {result.stderr}')
                        return None

                    local_temp_file = tempfile.NamedTemporaryFile()
                    conn.get(remote_temp_file, local_temp_file.name)

                    result = local_temp_file.read().decode('utf-8')
                    if len(result) == 0:
                        return None

                    # Return json object if result is json string, return raw string otherwise
                    try:
                        return json.loads(result)
                    except (ValueError, TypeError):
                        return result

                finally:
                    # delete remote temp file
                    # conn.run(f'rm {remote_temp_file}')
                    pass

        except Exception as e:
            logs.error(f'Exception when execute dumpstate: {e}')
            return None


    def get_stable_block_num(self) -> int:
        result = self.jrpc_query("eth_blockNumber", [])
        if result is None:
            result = self.cli_dbquery('-t latest_stable_block_number')
            return result
        else:
            return int(result, 16)

    def get_written_block_num(self) -> int:
        result = self.cli_dbquery('-t latest_written_block_number')
        return result

    def get_block_header_by_num(self, block_number: int):
        result = self.cli_dbquery(f'-t header -n {block_number}')
        return result

    def get_block_header_by_hash(self, hash: str):
        result = self.cli_dbquery(f'-t header --hash {hash}')
        return result


    def get_block_by_num(self, block_number: int):
        result = self.jrpc_query("eth_getBlockByNumber", [hex(block_number), True])
        if result is None:
            result = self.cli_dbquery(f'-t block -n {block_number}')

        return result

    def get_block_by_hash(self, hash: str):
        result = self.jrpc_query("eth_getBlockByHash", [hash, True])
        if result is None:
            result = self.cli_dbquery(f'-t block --hash {hash}')

        return result


    def get_tx(self, tx_hash: str):
        result = self.jrpc_query("eth_getTransactionByHash", [tx_hash])
        if result is None:
            result = self.cli_dbquery(f'-t tx --hash {tx_hash}')

        return result

    def get_receipt(self, tx_hash: str):
        result = self.jrpc_query("eth_getTransactionReceipt", [tx_hash])
        if result is None:
            result = self.cli_dbquery(f'-t receipt --hash {tx_hash}')

        return result


    def get_code(self, addr: str):
        result = self.jrpc_query("eth_getCode", [addr, "latest"])
        if result is None:
            result = self.cli_dbquery(f'-t code -a {addr}')
        return result

    def get_nonce(self, addr: str):
        result = self.jrpc_query("eth_getTransactionCount", [addr, "latest"])
        if result is None:
            result = self.cli_dbquery(f'-t account -a {addr}')
            if result is None:
                return None
            else:
                return int(result["nonce"], 10)
        else:
            return int(result, 16)

    def get_balance(self, addr: str):
        result = self.jrpc_query("eth_getBalance", [addr, "latest"])
        if result is None:
            result = self.cli_dbquery(f'-t account -a {addr}')
            if result is None:
                return None
            else:
                return int(result["balance"], 10)
        else:
            return int(result, 16)

    def get_state_by_num(self, block_number: int):
        return self.cli_dumpstate(f'-n {block_number}')

def compare_json(json1, json2, path=''):
    if isinstance(json1, dict) and isinstance(json2, dict):
        keys1 = set(json1.keys())
        keys2 = set(json2.keys())

        for key in keys1.union(keys2):
            new_path = f"{path}/{key}" if path else key
            if key in keys1 and key in keys2:
                compare_json(json1[key], json2[key], new_path)
            elif key in keys1:
                print(f"Key '{new_path}' found in first JSON but not in second JSON")
            else:
                print(f"Key '{new_path}' found in second JSON but not in first JSON")

    elif isinstance(json1, list) and isinstance(json2, list):
        len1 = len(json1)
        len2 = len(json2)
        for i in range(max(len1, len2)):
            new_path = f"{path}[{i}]"
            if i < len1 and i < len2:
                compare_json(json1[i], json2[i], new_path)
            elif i < len1:
                print(f"Index '{new_path}' found in first JSON but not in second JSON")
            else:
                print(f"Index '{new_path}' found in second JSON but not in first JSON")
    else:
        if json1 != json2:
            print(f"Value at '{path}' differs: {json1} != {json2}")

def diff(domain1: Composer, domain2: Composer, start: str):
    # Get start block number
    if start == 'written':
        print("Getting latest written block num")
        search_num = min(domain1.get_written_block_num(), domain2.get_written_block_num())
    elif start == 'stable':
        print("Getting latest stable block num")
        search_num = min(domain1.get_stable_block_num(), domain2.get_stable_block_num())
    else:
        search_num = int(start, 10)

    print(f"Start comparing at num {search_num}")
    if search_num is None:
        logs.error('Can\'t diff block because can\'t get block number')
        return

    # Get header & compare block hash until find the forked block
    forked_block_num = None
    unforked_block_num = None

    while unforked_block_num is None and search_num >= 0:
        logs.info('Compare hash of block {}'.format(search_num))

        block1 = domain1.get_block_by_num(search_num)
        block2 = domain2.get_block_by_num(search_num)

        if block1['hash'] != block2['hash']:
            forked_block_num = search_num
        else:
            unforked_block_num = search_num

        search_num -= 1

    if forked_block_num is None:
        print('No forked block found')
    else:
        print('Forked block found at block {}'.format(forked_block_num))
        block1 = domain1.get_block_by_num(forked_block_num)
        block2 = domain2.get_block_by_num(forked_block_num)

        compare_json(block1, block2)

def diffstatefork(domain1: Composer, domain2: Composer, start: str):
    search_num = int(start, 10)

    print(f"Statefork comparing at num {search_num}")
    if search_num is None:
        logs.error('Can\'t diff block because can\'t get block number')
        return

    state1 = domain1.get_state_by_num(search_num)
    state2 = domain2.get_state_by_num(search_num)
    compare_json(state1, state2)

