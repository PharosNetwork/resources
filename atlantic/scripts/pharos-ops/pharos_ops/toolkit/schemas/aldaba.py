#!/usr/bin/env python3
# coding=utf-8
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema
from pharos_ops.toolkit.common_types import MyGridConfig

@dataclass
class LogItem:
    filename: str = field(default='', metadata={'required': False})
    flush: bool = field(default=False, metadata={'required': False})
    level: str = field(default='info', metadata={'required': False})
    max_file_size: int = field(default=209715200, metadata={'required': False})
    max_files: int = field(default=100, metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class AldabaStartupConfig:
    config: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})
    init_config: Dict[str, Any] = field(default_factory=dict, metadata={'required': True})
    log: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    parameters: Dict[str, str] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class MonitorConfig:
    enable_pamir_cetina: bool = field(default=False, metadata={'required': False})
    pamir_cetina_push_address: str = field(default='', metadata={'required': False})
    pamir_cetina_push_port: int = field(default=80, metadata={'required': False})
    pamir_cetina_push_interval: int = field(default=5, metadata={'required': False})
    pamir_cetina_job_name: str = field(default='', metadata={'required': False})
    pamir_cetina_instance_name: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True

@dataclass
class SecretConfig:
    domain_key: str = field(default='', metadata={'required': False})
    stabilizing_key: str = field(default='', metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class AldabaConfig:
    startup_config: AldabaStartupConfig = field(default_factory=AldabaStartupConfig, metadata={'required': True})
    monitor_config: Dict[str, Optional[Any]] = field(default_factory=dict, metadata={'required': False})
    secret_config: SecretConfig = field(default_factory=SecretConfig, metadata={'required': False})

    class Meta:
        ordered: bool = True



@dataclass
class CubenetInner:
    p2p: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})
    admin: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})
    metrics: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class CubenetOuter:
    cubenet: CubenetInner = field(default_factory=CubenetInner, metadata={'required': False})

    class Meta:
        ordered: bool = True



@dataclass
class MygridConfFile:
    log: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})
    config: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


# @dataclass
# class MygridEnvFile:
#     mygrid_env: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})

#     class Meta:
#         ordered: bool = True


@dataclass
class StorageConfig:
    mygrid_conf: MygridConfFile = field(default_factory=MygridConfFile, metadata={'required': False})
    mygrid_env: Dict[str, Any] = field(default_factory=dict, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class RootConfig(object):
    aldaba: AldabaConfig = field(default_factory=AldabaConfig, metadata={'required': True})
    cubenet: CubenetOuter = field(default_factory=CubenetOuter, metadata={'required': False})
    storage: StorageConfig = field(default_factory=StorageConfig, metadata={'required': False})

    class Meta:
        ordered: bool = True

RootConfigSchema = class_schema(RootConfig)