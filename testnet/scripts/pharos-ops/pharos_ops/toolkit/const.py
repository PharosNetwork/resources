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

LOCAL_IP = '127.0.0.1'
SERVER_IP = '0.0.0.0'

PARTITION_SIZE = 256
MSU_SIZE = 256
ETCD_ENABLE = 2
ETCD_USERNAME = 'admin'
ETCD_PASSWORD = '123abc'
ETCD_TIMEOUT = 5000
ETCD_RETRY_SLEEP_TIME = 1
DOCKER_USERNAME = ''
DOCKER_PASSWORD = ''

REGISTRY_TYPE_FILE = 'file'
REGISTRY_TYPE_SECRET = 'secret'

TPL_LAUNCH_PATH = 'launch.tpl.conf'
TPL_CORE_LIMIT = 'unlimited'
TPL_ETCD_API_VERSION = '3'
TPL_ASAN_OPS = {
    'detect_leaks': 'false',
    'leak_check_at_exit': 'false',
    'disable_coredump': '0',
    'unmap_shadow_on_exit': '1',
    'abort_on_error': '1'
}
TPL_META_EPHEMERAL_EXPIRE_MS = '5000'
TPL_META_KEEPALIVE_INTERVAL_MS = '3000'

SVC = 'svc'
SVC_MNG_SH = 'mng.sh'
SVC_ENV = 'env.json'
STORAGE_BIN = 'mygrid_service'
ETCD_BIN = 'etcd'
ETCD_CTL_BIN = 'etcdctl'
SVC_CONF = 'svc.conf'
SVC_META_TOOL = 'meta_tool'

PHAROS = 'pharos'
PHAROS_LIGHT = 'pharos_light'
PHAROS_VERSION = 'VERSION'
EVMONE_SO = 'libevmone.so'

PHAROS_BIN = 'pharos'
PHAROS_BIN_LIGHT = 'pharos_light'
PHAROS_GENESIS_CONF = 'genesis.conf'
PHAROS_LAUNCH_CONF = 'launch.conf'
PHAROS_CLI = 'pharos_cli'


SERVICE_ETCD = 'etcd'
SERVICE_PORTAL = 'portal'
SERVICE_DOG = 'dog'
SERVICE_TXPOOL = 'txpool'
SERVICE_CONTROLLER = 'controller'
SERVICE_COMPUTE = 'compute'
SERVICE_STORAGE = 'mygrid'
# SERVICE_ULTRA = 'ultra'
SERVICE_LIGHT = 'light'

CHAIN_PROTOCOL = 'chain_protocol'
PROTOCOL_NATIVE = 'native'
PROTOCOL_EVM = 'evm'
PROTOCOL_ALL = 'all'

LIGHT_DEPLOY_MODE = 'light'
ULTRA_DEPLOY_MODE = 'ultra'

# etcd必须放第一个
# 服务间虽无依赖，但一般按该列表顺序启动，逆序停止
SERVICES = [SERVICE_ETCD, SERVICE_STORAGE, SERVICE_TXPOOL, SERVICE_COMPUTE, SERVICE_CONTROLLER, SERVICE_DOG, SERVICE_PORTAL]

CLI_BINARYS = [PHAROS_CLI, ETCD_CTL_BIN, EVMONE_SO, SVC_META_TOOL]

BINARY_MAP = {
    SERVICE_ETCD: ETCD_BIN,
    SERVICE_STORAGE: STORAGE_BIN,
    SERVICE_PORTAL: PHAROS_BIN,
    SERVICE_DOG: PHAROS_BIN,
    SERVICE_TXPOOL: PHAROS_BIN,
    SERVICE_CONTROLLER: PHAROS_BIN,
    SERVICE_COMPUTE: PHAROS_BIN,
    SERVICE_LIGHT: PHAROS_BIN_LIGHT,
}

ENV_ASAN_OPTIONS = 'ASAN_OPTIONS'

ENV_CHAIN_ID = 'CHAIN_ID'
ENV_DOMAIN_LABEL = 'DOMAIN_LABEL'

ENV_POD_HOST = 'POD_HOST'
ENV_POD_PORT = 'POD_PORT'
ENV_POD_NAME = 'POD_NAME'
ENV_POD_UUID = 'POD_UUID'

ENV_PARTITION_LIST = 'PARTITION_LIST'

ENV_STORAGE_ETCD = 'STORAGE_ETCD'
ENV_STORAGE_ID = 'STORAGE_ID'
ENV_STORAGE_PATH = 'STORAGE_PATH'

MYGRID_CONFIG_NAME = 'mygrid'
META_SERVICE_CONFIG_NAME = 'meta_service'

MYGRID_GENESIS_CONFIG_FILENAME = f'{MYGRID_CONFIG_NAME}_genesis.conf'
META_SERVICE_CONFIG_FILENAME = f'{META_SERVICE_CONFIG_NAME}.conf'

DRIVER_NAME_SQLITE3 = 'sqlite3'
DRIVER_NAME_POSTGRES = 'postgres'

MYGRID_CONF_JSON_FILENAME = 'mygrid.conf.json'
MYGRID_LIGHT_ENV_JSON_FILENAME = 'mygrid.light.env.json'
MYGRID_ULTRA_ENV_JSON_FILENAME = 'mygrid.ultra.env.json'
MYGRID_ENV_JSON_FILENAME = 'mygrid.env.json'
MONITOR_CONF_JSON_FILENAME = 'monitor.conf'

MYGRID_CLIENT_JSON = f'''
{{
  "{MYGRID_CONFIG_NAME}": {{
    "mygrid_client_id" : "0",
    "mygrid_conf_path" : "../conf/{MYGRID_CONF_JSON_FILENAME}",
    "mygrid_env_path" : "../conf/{MYGRID_ENV_JSON_FILENAME}"
  }}
}}
'''

META_SERVICE_JSON = f'''
{{
  "{META_SERVICE_CONFIG_NAME}": {{
    "myid": 0,
    "etcd": {{
      "enable": 0,
      "timeout": 5000,
      "retry_sleep_time": 1,
      "endpoints": []
    }},
    "data_path": "../data"
  }}
}}
'''

CLI_JSON = '''
{
  "chain_id": "",
  "domain_id": "",
  "etcd": {
    "enable": 0,
    "timeout": 5000,
    "endpoints": []
  },
  "data_path": "../data"
}
'''

PREDEFINED_DOMAINS = ["domain0", "domain1", "domain2", "domain3", "domain4", "domain5", "domain6", "domain7"]
