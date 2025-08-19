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
from aldaba_ops.toolkit import compose, utils, logs

import os
import base64

from typing import List, Dict, Any


class ConfigRegistry(object):
    """Config like 'global.conf, portal.conf, svc.conf' provider"""

    _registry_compose: compose.RegistryCompose

    def __init__(self, registry_compose: compose.RegistryCompose):
        self._registry_compose = registry_compose

    def get_config_path(self, conf_name: str) -> str:
        if os.path.splitext(conf_name)[-1] == '':
            conf_name += '.conf'
        path = os.path.join(self._registry_compose.dir, conf_name)
        utils.must_path_exists(path)
        return path

    def get_config(self, conf_name: str) -> Dict[str, Any]:
        conf_path = self.get_config_path(conf_name)
        logs.info(f"{conf_path}")
        return utils.load_file(conf_path)


class SecretRegistry(object):
    """Secret like certs & keys which plaintext at deploy.json provider"""

    _registry_compose: compose.RegistryCompose
    _secret_conf: Dict[str, Any]

    def __init__(self, registry_compose: compose.RegistryCompose):
        self._registry_compose = registry_compose
        secret_conf = utils.load_file(os.path.join(registry_compose.dir, '.secret'))
        if 'root' not in secret_conf:
            logs.fatal('failed to init secret registry, secret conf root is invalid')
        if 'data' not in secret_conf:
            logs.fatal('failed to init secret registry, secret conf data is invalid')
        self._secret_conf = secret_conf

    def get_secret(self, key: str) -> str:
        val = utils.get_dict_keys_val(self._secret_conf['data'], key)
        if not isinstance(val, str):
            logs.fatal('failed to get secret, key {} val {} is invalid'.format(key, val))
        if key.endswith('passwd'):
            # todo 判断 passwd_hanlder
            pass
        elif key.endswith('file'):
            # todo 判断 file_hanlder
            file_path = utils.get_abs_path(self._secret_conf['root'], val)
            utils.must_path_exists(file_path)
            with open(file_path, 'r') as file:
                bcontent = file.read().encode()
                val = base64.b64encode(bcontent).decode()
        return val


class ArtifactRegistry(object):
    """Artifact of abi file provider"""

    _registry_compose: compose.RegistryCompose

    def __init__(self, registry_compose: compose.RegistryCompose):
        self._registry_compose = registry_compose

    def get_artifact_path(self, artifact_name: str=None) -> str:
        if artifact_name is None:
            return self._registry_compose.dir
        path = os.path.join(self._registry_compose.dir, artifact_name)
        utils.must_path_exists(path)
        return path


class BinaryRegistry(object):
    """Binary of aldaba and svc provider"""

    _registry_compose: compose.RegistryCompose

    def __init__(self, registry_compose: compose.RegistryCompose):
        self._registry_compose = registry_compose

    def get_binary_path(self, bin_name: str) -> str:
        path = os.path.join(self._registry_compose.dir, bin_name)
        utils.must_path_exists(path)
        return path

    def get_svc_bin_dir(self) -> str:
        return os.path.join(self._registry_compose.dir, '..')


class DockerRegistry(object):
    """Docker of aldaba and svc provider"""

    _registry_compose: compose.DockerRegistryCompose

    def __init__(self, registry_compose: compose.DockerRegistryCompose):
        self._registry_compose = registry_compose
