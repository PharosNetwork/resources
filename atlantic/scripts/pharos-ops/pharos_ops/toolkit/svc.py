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
from pharos_ops.toolkit import compose, utils, const, schema, logs

import os

from typing import List, Dict, Any, NamedTuple


class StorageNode(NamedTuple):
    """Data class of storage node at env.json"""

    ip: str = ''
    port: str = ''
    rest_port: str = None
    msu: str = ''
    myid: int = 0
    deploydir: str = ''
    user: str = ''

    @property
    def rpc_url(self):
        return 'tcp://{}:{}'.format(self.ip, self.port)

    # suppress warnings
    def as_dict(self):
        return self._asdict()


class EtcdNode(NamedTuple):
    """Data class of etcd node at env.json"""

    ip: str = ''
    port: str = ''
    peer_port: str = ''
    deploydir: str = ''
    user: str = ''

    @property
    def peer_url(self):
        return 'http://{}:{}'.format(self.ip, self.peer_port)

    @property
    def client_url(self):
        return 'http://{}:{}'.format(self.ip, self.port)

    # suppress warnings
    def as_dict(self):
        return self._asdict()


def update_svc_env(svc_run_dir: str, svc_env: Dict[str, Any]) -> str:
    """
    Update env.json at svc shells run root
    :param svc_run_dir: svc shells run root
    :param svc_env: json to update
    :return env file path
    """

    env_file_path = os.path.join(svc_run_dir, const.SVC_ENV)
    try:
        env_data = utils.load_file(env_file_path)
    except:
        env_data = {}
    for k, v in svc_env.items():
        utils.update_dict_keys(env_data, k, v)
    utils.dump_file(env_data, env_file_path)

    return env_file_path


def update_svc_meta(svc_run_dir: str, domain_label: str, svc_meta: Dict[str, Any]) -> str:
    """
    Update meta_data.$domain_label.json at svc shells run root
    :param svc_run_dir: svc shells run root
    :param domain_label: domain label
    :param svc_meta: json to update
    :return meta data file path
    """

    meta_file_path = os.path.join(svc_run_dir, 'meta_data.{}.json'.format(domain_label))
    meta_data = utils.load_file(meta_file_path)
    # update meta
    for k, v in svc_meta.items():
        utils.update_dict_keys(meta_data, k, v)
    utils.dump_file(meta_data, meta_file_path)

    return meta_file_path


class SvcManager(object):
    """Manager class of svc shells"""

    _svc_compose: compose.SvcCompose = None
    # _svc_conf: Dict[str, Any] = {}

    _bin_dir: str = '../../..'

    def __init__(self, svc_compose: compose.SvcCompose, svc_bin_dir: str = '../../..'):
        self._svc_compose = svc_compose

        self._bin_dir = svc_bin_dir

        utils.must_path_exists(svc_compose.run_dir)

    @property
    def run_dir(self):
        return self._svc_compose.run_dir

    @property
    def data_dir(self) -> str:
        return self._svc_compose.data_dir

    # todo get from storage at meta data file
    def get_svc_conf(self, myid: str) -> Dict[str, Any]:
        return {
            'storage': {
                'myid': myid,
                'etcd': schema.SvcEtcdComposeSchema().dump(self._svc_compose.etcd),
                'data_path': self.data_dir
            }
        }

    def deploy_svc(self, domain_label: str):
        """
        Deploy storage nodes of env.json
        :param domain_label: domain label
        """

        logs.info('svc mng deploy svc {}'.format(domain_label))

        # step1 execute bash mng.sh -e $domain_label svc_deploy
        shell_name = 'export MYC_ETCD_ENABLE_FLAG={} && cd {} && bash mng.sh -e {} svc_deploy'.format(
            self._svc_compose.etcd.enable, self.run_dir, domain_label)
        utils.must_exec_run(shell_name)

    def deploy_etcd(self, domain_label: str):
        """
        Deploy etcd cluster of env.json
        :param domain_label: domain label
        """

        logs.info('svc mng deploy etcd {}'.format(domain_label))

        shell_name = 'cd {} && bash mng.sh -e {} etcd_deploy'.format(self.run_dir, domain_label)
        utils.must_exec_run(shell_name)

    def start_etcd(self, domain_label: str):
        """
        Start etcd cluster of env.json
        :param domain_label: domain label
        """

        logs.info('svc mng start etcd {}'.format(domain_label))

        shell_name = 'cd {} && bash mng.sh -e {} etcd_start'.format(self.run_dir, domain_label)
        utils.must_exec_run(shell_name)

    def stop_etcd(self, domain_label: str):
        """
        Stop etcd cluster of env.json
        :param domain_label: domain label
        """

        logs.info('svc mng stop etcd {}'.format(domain_label))

        shell_name = 'cd {} && bash mng.sh -e {} etcd_kill'.format(self.run_dir, domain_label)
        utils.must_exec_run(shell_name)

    def setmeta_svc(self, domain_label: str):
        """
        Set meta of meta_data.$domain_label.json after deploy svc.
        Storage depend meta to initalize.
        Start etcd first if not deploy in mono mode.
        :param domain_label: domain label
        """

        logs.info('svc mng setmeta svc {}'.format(domain_label))

        # step1 update storage and meta to meta_data.$domain_label.json
        if 'storage.data_path' not in self._svc_compose.meta:
            self._svc_compose.meta['storage.data_path'] = self.data_dir
        update_svc_meta(self.run_dir, domain_label, self._svc_compose.meta)

        # step2 execute bash mng.sh -e $domain_label svc_setmeta
        shell_name = 'cd {} && bash mng.sh -e {} svc_setmeta'.format(self.run_dir, domain_label)
        utils.must_exec_run(shell_name)
