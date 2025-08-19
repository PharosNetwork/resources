#!/usr/bin/env python3
# coding=utf-8
"""
    Copyright (C) 2020 Ant Financial. All rights reserved.

    Desc     : Aldaba2.0 Operation Tools
    History  :
    License  : Ant Financial proprietary/confidential.

    Python Version : 3.6.8
    Created by youxing.zys
    Date: 2022/12/06
"""
from aldaba_ops.toolkit import compose, config

from marshmallow_dataclass import class_schema

DeployConfigSchema = class_schema(config.DeployConfig)
MyGridConfigSchema = class_schema(config.MyGridConfig)
SecretConfigSchema = class_schema(config.SecretConfig)
LaunchConfigSchema = class_schema(config.LaunchConfig)

DomainComposeSchema = class_schema(compose.DomainCompose)
ServiceComposeSchema = class_schema(compose.ServiceCompose)
SvcEtcdComposeSchema = class_schema(compose.SvcEtcdCompose)
