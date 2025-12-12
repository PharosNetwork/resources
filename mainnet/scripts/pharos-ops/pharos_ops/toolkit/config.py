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
import os

from pharos_ops.toolkit import validate

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from pharos_ops.toolkit.common_types import MyGridConfig

@dataclass
class DomainSecretConfig(object):
    key_file: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    key_type: str = field(default='', metadata={'required': True, 'validate': validate.KeyType()})
    key_passwd: str = field(default='123abc', metadata={'required': False})

    class Meta:
        ordered: bool = True


# @dataclass
# class ClientSecretConfig(object):
#     ca_cert_file: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
#     cert_file: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
#     key_file: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
#     key_type: str = field(default='', metadata={'required': True, 'validate': validate.KeyType()})
#     key_passwd: str = field(default='123abc', metadata={'required': False})

#     class Meta:
#         ordered: bool = True


@dataclass
class SecretConfig(object):
    domain: DomainSecretConfig = field(default_factory=DomainSecretConfig, metadata={'required': True})
    # client: ClientSecretConfig = field(default_factory=ClientSecretConfig, metadata={'required': True})

    class Meta:
        ordered: bool = True


@dataclass
class EtcdConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    peer_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})

    class Meta:
        ordered: bool = True


@dataclass
class PortalConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})
    client_tcp_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_http_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_ws_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_wss_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})

    class Meta:
        ordered: bool = True


@dataclass
class DogConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})
    domain_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})

    class Meta:
        ordered: bool = True


@dataclass
class TxpoolConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})
    partitions: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})

    class Meta:
        ordered: bool = True


@dataclass
class ControllerConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})

    class Meta:
        ordered: bool = True


@dataclass
class ComputeConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})

    class Meta:
        ordered: bool = True


@dataclass
class StorageConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    rpc_port: int = field(default=0, metadata={'required': True, 'validate': validate.PortType()})
    msu: Optional[str] = field(default='', metadata={'required': False, 'validate': validate.NonEmpty()})

    class Meta:
        ordered: bool = True


@dataclass
class UltraConfig(object):
    etcd: List[EtcdConfig] = field(default_factory=list, metadata={'required': True, 'validate': validate.NonEmpty()})
    portal: List[PortalConfig] = field(default_factory=list,
                                       metadata={'required': True, 'validate': validate.NonEmpty()})
    dog: List[DogConfig] = field(default_factory=list, metadata={'required': True, 'validate': validate.NonEmpty()})
    txpool: List[TxpoolConfig] = field(default_factory=list,
                                       metadata={'required': True, 'validate': validate.NonEmpty()})
    controller: List[ControllerConfig] = field(default_factory=list,
                                               metadata={'required': True, 'validate': validate.NonEmpty()})
    compute: List[ComputeConfig] = field(default_factory=list,
                                         metadata={'required': True, 'validate': validate.NonEmpty()})
    storage: List[StorageConfig] = field(default_factory=list,
                                         metadata={'required': True, 'validate': validate.NonEmpty()})

    class Meta:
        ordered: bool = True


@dataclass
class LightConfig(object):
    ip: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    client_tcp_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_http_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_ws_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    client_wss_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    domain_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    rpc_port: int = field(default=0, metadata={'required': False, 'validate': validate.PortType()})
    # storage_path: str = field(default='../data', metadata={'required': False, 'validate': validate.NonEmpty()})
    class Meta:
        ordered: bool = True


@dataclass
class DeployConfig(object):
    """Data class of deploy.json"""

    chain_id: str = field(default='pharos', metadata={'required': False, 'validate': validate.NonEmpty()})
    domain_label: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    domain_role: int = field(default=0, metadata={'required': True, 'validate': validate.OneOf([0, 1, 2])})
    genesis_conf: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    mygrid: MyGridConfig = field(default_factory=MyGridConfig, metadata={'required': True})
    secret: SecretConfig = field(default_factory=SecretConfig, metadata={'required': True})
    run_user: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    run_root: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    deploy_dir: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    version: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})
    docker_mode: bool = field(default=False, metadata={'required': False})
    docker_registry: str = field(default='', metadata={'required': False})
    ultra: Optional[UltraConfig] = field(default=None, metadata={'required': False})
    light: Optional[LightConfig] = field(default=None, metadata={'required': False})

    @property
    def deploy_root(self):
        return os.path.join(self.deploy_dir, self.chain_id, self.domain_label)

    class Meta:
        ordered: bool = True


@dataclass
class LaunchConfig(object):
    """Data class of launch.conf"""

    parameters: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    init_config: Dict[str, Optional[Any]] = field(default=None, metadata={'required': False})

    class Meta:
        ordered: bool = True
