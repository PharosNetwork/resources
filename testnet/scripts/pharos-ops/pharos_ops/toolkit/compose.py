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
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ServiceCompose(object):
    service: str = field(default='', metadata={'required': True})
    ip: str = field(default='', metadata={'required': True})
    # deploy_dir: str = field(default='', metadata={'required': False})
    conf_file: str = field(default='', metadata={'required': False})
    conf: Dict[str, Optional[Any]] = field(default=None, metadata={'required': False})
    env: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class RegistryCompose(object):
    registry_type: str = field(default='file', metadata={'required': False})
    dir: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class DockerRegistryCompose(object):
    registry: str = field(default='', metadata={'required': True})
    username: str = field(default='', metadata={'required': True})
    password: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True


# @dataclass
# class MetaCompose(object):
#     pass

@dataclass
class SvcEtcdCompose(object):
    enable: int = field(default=0, metadata={'required': True})
    username: str = field(default='', metadata={'required': False})
    password: str = field(default='', metadata={'required': False})
    timeout: int = field(default=0, metadata={'required': False})
    endpoints: List[str] = field(default_factory=list, metadata={'required': True})

    class Meta:
        ordered: bool = True


@dataclass
class SvcCompose(object):
    run_dir: str = field(default='', metadata={'required': True})
    # env: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    data_dir: str = field(default='', metadata={'required': True})
    etcd: SvcEtcdCompose = field(default_factory=SvcEtcdCompose, metadata={'required': False})
    meta: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class DomainCompose(object):
    """Data class of $domain_Label.json"""

    chain_id: str = field(default='', metadata={'required': True})
    genesis_conf: str = field(default='', metadata={'required': True})
    domain_label: str = field(default='', metadata={'required': True})
    version: str = field(default='', metadata={'required': True})
    config: RegistryCompose = field(default_factory=RegistryCompose, metadata={'required': False})
    secret: RegistryCompose = field(default_factory=RegistryCompose, metadata={'required': False})
    artifact: RegistryCompose = field(default_factory=RegistryCompose, metadata={'required': False})
    binary: RegistryCompose = field(default_factory=RegistryCompose, metadata={'required': False})
    docker: DockerRegistryCompose = field(default_factory=DockerRegistryCompose, metadata={'required': False})
    svc: SvcCompose = field(default_factory=SvcCompose, metadata={'required': False})
    meta: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})
    cluster: Dict[str, ServiceCompose] = field(default_factory=dict, metadata={'required': True})
    run_user: str = field(default='', metadata={'required': True})
    docker_mode: bool = field(default=False, metadata={'required': False})
    light_mode: bool = field(default=False, metadata={'required': False})
    deploy_dir: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True
