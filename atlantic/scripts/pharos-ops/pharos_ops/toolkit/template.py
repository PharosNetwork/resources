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
from pharos_ops.toolkit import schema, utils, config, const, compose

import copy
import json

from typing import List, Dict, Any


class TemplateFactory(object):
    """Factory class of launch.tpl.conf"""

    _launch_tpl: config.LaunchConfig = None
    _env_tpl: Dict[str, Any] = {}

    def __init__(self, template_file_path: str = ''):
        launch_tpl = config.LaunchConfig()
        if template_file_path != '':
            template_data = utils.load_file(template_file_path)
            launch_tpl = schema.LaunchConfigSchema().load(template_data)

        #  launch_tpl.parameters.update({
            #  '/SetLimit/core': const.TPL_CORE_LIMIT,
            #  '/SetEnv/ASAN_OPTIONS': ':'.join([k + '=' + v for k, v in const.TPL_ASAN_OPS.items()])
        #  })
        self._launch_tpl = launch_tpl

    def update_tmpl_params_chain(self, chain_id: str):
        self._launch_tpl.parameters['/SetEnv/' + const.ENV_CHAIN_ID] = chain_id

    def update_tmpl_params_domain(self, domain_label: str):
        self._launch_tpl.parameters['/SetEnv/' + const.ENV_DOMAIN_LABEL] = domain_label

    def update_tmpl_params_etcd(self, etcd_compose: compose.SvcEtcdCompose):
        etcd_data = schema.SvcEtcdComposeSchema().dump(etcd_compose)
        etcd_str = json.dumps(etcd_data)
        self._launch_tpl.parameters['/SetEnv/' + const.ENV_STORAGE_ETCD] = etcd_str

    def update_tmpl_config(self, config: Dict[str, Any]):
        self._launch_tpl.config.update(config)

    def get_launch_tpl(self) -> config.LaunchConfig:
        return copy.deepcopy(self._launch_tpl)

    def update_tmpl_env_chain(self, chain_id: str):
        self._env_tpl[const.ENV_CHAIN_ID] = chain_id

    def update_tmpl_env_domain(self, domain_label: str):
        self._env_tpl[const.ENV_DOMAIN_LABEL] = domain_label

    def update_tmpl_env_svc(self, svc_compose: compose.SvcCompose):
        etcd_data = schema.SvcEtcdComposeSchema().dump(svc_compose.etcd)
        etcd_str = json.dumps(etcd_data)
        self._env_tpl[const.ENV_STORAGE_ETCD] = etcd_str
        self._env_tpl[const.ENV_STORAGE_ID] = '0'
        self._env_tpl[const.ENV_STORAGE_PATH] = svc_compose.data_dir

    def get_env_tpl(self) -> config.LaunchConfig:
        return self._env_tpl.copy()
