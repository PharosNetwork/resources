#!/usr/bin/env python3
# coding=utf-8
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema
from pharos_ops.toolkit.common_types import MyGridConfig
@dataclass
class SecretFiles(object):
    key_type: str = field(default='prime256v1', metadata={'required': True})
    files: Dict[str, str] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class Secret(object):
    domain: SecretFiles = field(default_factory=SecretFiles, metadata={'required': True})
    client: SecretFiles = field(default_factory=SecretFiles, metadata={'required': True})

    class Meta:
        ordered: bool = True

@dataclass
class Docker(object):
    enable: bool = field(default=False, metadata={'required': True})
    registry: str = field(default='', metadata={'required': True})

    class Meta:
        ordered: bool = True

@dataclass
class Metrics(object):
    enable: bool = field(default=False, metadata={'required': True})
    push_address: str = field(default='', metadata={'required': True})
    push_port: str = field(default='', metadata={'required': True})
    job_name: str = field(default='', metadata={'required': True})
    push_interval: str = field(default='', metadata={'required': True})

@dataclass
class Common(object):
    env: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    gflags: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    metrics: Metrics = field(default_factory=Metrics)

    class Meta:
        ordered: bool = True

@dataclass
class Instance(object):
    service: str = field(default='', metadata={'required': True})
    name: str = field(default='', metadata={'required': False})
    ip: str = field(default='', metadata={'required': True})
    dir: str = field(default='', metadata={'required': False})      # 默认为$deploy_dir/$instance_name, 支持分别指定
    args: List[str] = field(default_factory=list, metadata={'required': False})
    env: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    gflags: Dict[str, str] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class Domain(object):
    """Data class of $domain_Label.json"""

    build_root: str = field(default='', metadata={'required': True})
    chain_id: str = field(default='', metadata={'required': True})
    chain_protocol: str = field(default='native', metadata={'required': False})
    domain_label: str = field(default='', metadata={'required': True})
    version: str = field(default='', metadata={'required': True})
    run_user: str = field(default='', metadata={'required': True})
    deploy_dir: str = field(default='', metadata={'required': True})
    genesis_conf: str = field(default='../conf/genesis.conf', metadata={'required': True})
    mygrid: MyGridConfig = field(default_factory=MyGridConfig, metadata={'required': True})
    secret: Secret = field(default_factory=Secret, metadata={'required': True})
    use_generated_keys : bool = field(default=False, metadata={'required': False})
    enable_dora : bool = field(default=False, metadata={'required': False})
    key_passwd : str = field(default='123abc', metadata={'required': False})
    portal_ssl_pass : str = field(default='123abc', metadata={'required': False})
    enable_setkey_env: bool = field(default=True, metadata={'required': False}) # 设置pass env开关，默认打开    
    docker: Docker = field(default_factory=Docker, metadata={'required': True})
    common: Common = field(default_factory=Common, metadata={'required': False})
    cluster: Dict[str, Instance] = field(default_factory=dict, metadata={'required': True})
    initial_stake_in_gwei: int = field(default=1000000000, metadata={'required': False})

    class Meta:
        ordered: bool = True

DomainSchema = class_schema(Domain)
