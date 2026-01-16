#!/usr/bin/env python3
# coding=utf-8

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema

from pharos_ops.toolkit.common_types import MyGridConfig

@dataclass
class Docker(object):
    enable: bool = field(default=False, metadata={'required': True})
    registry: str = field(default='', metadata={'required': True})
    #  image: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class StorageExtra(object):
    args: List[str] = field(default_factory=list, metadata={'required': False})
    env: Dict[str, str] = field(default_factory=dict, metadata={'required': False})

@dataclass
class Extra(object):
    args: List[str] = field(default_factory=list, metadata={'required': False})
    env: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    gflags: Dict[str, str] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class Common(object):
    env: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    gflags: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    monitor_config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class Node(object):
    deploy_ip: str = field(default='127.0.0.1', metadata={'required': True})
    host: str = field(default='127.0.0.1', metadata={'required': True})
    start_port: int = field(default=20000, metadata={'required': True})
    instances: str = field(default='', metadata={'required': True})

@dataclass
class DomainSummary(object):
    deploy_dir: str = field(default='', metadata={'required': False})
    domain_role: int = field(default=0, metadata={'required': False})
    key_passwd : str = field(default='', metadata={'required': False})
    portal_ssl_pass : str = field(default='', metadata={'required': False})
    domain_port: int = field(default=19000, metadata={'required': True})
    # client_tcp_port: int = field(default=18000, metadata={'required': True})
    client_ws_port: int = field(default=0, metadata={'required': False})
    # client_wss_port: int = field(default=0, metadata={'required': False})
    client_http_port: int = field(default=0, metadata={'required': False})
    cluster: List[Node] = field(default_factory=list, metadata={'required': True})
    initial_stake_in_gwei: int = field(default=1000000000, metadata={'required': False})
    enable_setkey_env: bool = field(default=True, metadata={'required': False}) # 设置pass env开关，默认打开

    class Meta:
        ordered: bool = True

@dataclass
class Deploy(object):
    """Data class of deploy.json"""

    build_root: str = field(default='', metadata={'required': True})
    chain_id: str = field(default='', metadata={'required': True})
    chain_protocol: str = field(default='native', metadata={'required': False})
    version: str = field(default='', metadata={'required': True})
    run_user: str = field(default='', metadata={'required': True})
    deploy_root: str = field(default='', metadata={'required': False})
    admin_addr: str = field(default='2cc298bdee7cfeac9b49f9659e2f3d637e149696', metadata={'required': False})
    proxy_admin_addr: str = field(default='0278872d3f68b15156e486da1551bcd34493220d', metadata={'required': False})
    genesis_tpl: str = field(default='../conf/genesis.tpl.conf', metadata={'required': True})
    mygrid: MyGridConfig = field(default_factory=MyGridConfig, metadata={'required': True})
    running_conf: str = field(default='../conf/pharos.tpl.conf', metadata={'required': True})
    domain_key_type: str = field(default='', metadata={'required': True})
    # client_key_type: str = field(default='', metadata={'required': False})
    use_generated_keys : bool = field(default=False, metadata={'required': False})
    use_latest_version: bool = field(default=False, metadata={'required': False})
    docker: Docker = field(default_factory=Docker, metadata={'required': True})
    common: Common = field(default_factory=Common, metadata={'required': False})
    pharos: Extra = field(default_factory=Extra, metadata={'required': False})  # FIXME: 后续删掉, 使用common
    storage: StorageExtra = field(default_factory=Extra, metadata={'required': False})
    domains: Dict[str, DomainSummary] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True

DeploySchema = class_schema(Deploy)

