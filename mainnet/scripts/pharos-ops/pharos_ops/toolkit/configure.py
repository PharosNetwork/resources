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
from pharos_ops.toolkit import compose, template, config, schema, svc, utils, const, pharos, logs

import os

from typing import List, Dict, Any, Optional


class ConfigManager(object):
    """Manager class to parse deploy.json and generate $domain_label.json"""

    _deploy_conf_path: str = ''
    _deploy_config: config.DeployConfig = None
    _svc_run_dir: str = ''
    _secret_conf: Dict[str, Any] = None

    _run_root: str = ''
    _scripts_dir: str = ''
    _conf_dir: str = ''
    _artifact_dir: str = ''
    _bin_dir: str = ''

    _tpl_factory: template.TemplateFactory = None

    def __init__(self, deploy_file_path: str, svc_mng_dir: str, secret_conf: Dict[str, Any] = None):
        deploy_conf_path = os.path.abspath(deploy_file_path)
        utils.must_path_exists(deploy_conf_path)
        self._deploy_conf_path = deploy_conf_path
        self._secret_conf = secret_conf

        deploy_data = utils.load_file(deploy_file_path)
        deploy_config = schema.DeployConfigSchema().load(deploy_data)
        self._deploy_config = deploy_config

        scripts_dir = os.path.dirname(deploy_conf_path)
        self._scripts_dir = scripts_dir

        run_root = os.path.abspath(os.path.join(scripts_dir, '..'))
        self._run_root = run_root
        logs.debug('run_root: ' + run_root)

        svc_run_dir = os.path.abspath(os.path.join(scripts_dir, svc_mng_dir))
        self._svc_run_dir = svc_run_dir

        conf_dir = os.path.join(run_root, 'conf')
        utils.must_path_exists(conf_dir)
        self._conf_dir = conf_dir
        logs.debug('conf_dir: ' + conf_dir)

        artifact_dir = os.path.join(conf_dir, 'artifacts')
        utils.must_path_exists(artifact_dir)
        self._artifact_dir = artifact_dir
        logs.debug('artifact_dir: ' + artifact_dir)

        bin_dir = os.path.join(run_root, 'bin')
        utils.must_path_exists(bin_dir)
        self._bin_dir = bin_dir
        logs.debug('bin_dir: ' + bin_dir)

        tpl_launch_path = os.path.join(conf_dir, const.TPL_LAUNCH_PATH)
        if os.path.exists(tpl_launch_path):
            tpl_factory = template.TemplateFactory(tpl_launch_path)
        else:
            tpl_factory = template.TemplateFactory()
        tpl_factory.update_tmpl_env_chain(deploy_config.chain_id)
        tpl_factory.update_tmpl_env_domain(deploy_config.domain_label)
        self._tpl_factory = tpl_factory
        logs.debug('tpl_launch_path: ' + tpl_launch_path)

    @property
    def is_ultra(self) -> bool:
        return self._deploy_config.ultra is not None

    @property
    def is_mygrid_conf_adaptive_enabled(self) -> bool:
        return self._deploy_config.mygrid.conf.enable_adaptive

    @property
    def mygrid_conf_fpath(self) -> bool:
        return self._deploy_config.mygrid.conf.filepath

    @property
    def mygrid_env_fpath(self) -> bool:
        return self._deploy_config.mygrid.env.filepath

    @property
    def chain_id(self) -> str:
        return self._deploy_config.chain_id

    @property
    def domain_label(self) -> str:
        return self._deploy_config.domain_label

    @property
    def domain_dir(self) -> str:
        return '{}/{}/{}'.format(self._deploy_config.deploy_dir, self.chain_id, self.domain_label)

    @property
    def run_user(self) -> str:
        return self._deploy_config.run_user

    @property
    def partition_size(self) -> int:
        if self.is_ultra and len(self._deploy_config.ultra.txpool) > 0:
            return const.PARTITION_SIZE // len(self._deploy_config.ultra.txpool)
        return const.PARTITION_SIZE

    __etcd_token: str = None

    @property
    def etcd_token(self) -> str:
        if self.__etcd_token is not None:
            return self.__etcd_token
        self.__etcd_token = ''
        if not self.is_ultra:
            return self.__etcd_token
        __etcd_token = 'etcd_token_{}_{}'.format(self.domain_label, utils.get_tid())
        return self.__etcd_token

    __etcd_cluster: List[svc.EtcdNode] = None

    @property
    def etcd_cluster(self):
        if self.__etcd_cluster is not None:
            return self.__etcd_cluster
        self.__etcd_cluster = []
        if not self.is_ultra:
            return self.__etcd_cluster
        for idx, etcd_config in enumerate(self._deploy_config.ultra.etcd):
            node_name = const.SERVICE_ETCD + str(idx)
            node = svc.EtcdNode(ip=etcd_config.ip, port=str(etcd_config.client_port), peer_port=str(etcd_config.peer_port),
                                deploydir=os.path.join(self.domain_dir, node_name), user=self.run_user)
            self.__etcd_cluster.append(node)
        return self.__etcd_cluster

    __storage_nodes: Dict[str, svc.StorageNode] = None

    @property
    def storage_nodes(self) -> Dict[str, svc.StorageNode]:
        if self.__storage_nodes is not None:
            return self.__storage_nodes
        self.__storage_nodes = {}
        if not self.is_ultra:
            light_config = self._deploy_config.light
            node = svc.StorageNode(ip=light_config.ip, port=str(light_config.rpc_port), rest_port=None, msu='0-255',
                                   myid=0, deploydir=self.domain_dir, user=self.run_user)
            self.__storage_nodes[const.SERVICE_LIGHT] = node
            return self.__storage_nodes
        for idx, storage_config in enumerate(self._deploy_config.ultra.storage):
            node_name = const.SERVICE_STORAGE + str(idx)
            node = svc.StorageNode(ip=storage_config.ip, port=str(storage_config.rpc_port), rest_port=None, msu=storage_config.msu,
                                   myid=idx, deploydir=os.path.join(self.domain_dir, node_name), user=self.run_user)
            self.__storage_nodes[node_name] = node
        return self.__storage_nodes

    __service_ids: Dict[str, str] = {}
    def get_service_id(self, service_name: str) -> str:
        if service_name not in self.__service_ids:
            return service_name
        return self.__service_ids[service_name]

    __service_enum = {
        const.SERVICE_PORTAL: pharos.ServiceEnum.PORTAL,
        const.SERVICE_CONTROLLER: pharos.ServiceEnum.CONTROLLER,
        const.SERVICE_TXPOOL: pharos.ServiceEnum.TXPOOL,
        const.SERVICE_COMPUTE: pharos.ServiceEnum.COMPUTE,
        const.SERVICE_LIGHT: pharos.ServiceEnum.LIGHT,
    }
    def gen_service_id(self, service: str, idx: int) -> str:
        service_name = service + str(idx) if self.is_ultra else service
        if service not in self.__service_enum:
            return service_name
        uuid = pharos.get_pod_uuid(self.__service_enum[service], idx)
        self.__service_ids[service_name] = uuid
        return uuid

    def _get_config_compose(self) -> compose.RegistryCompose:
        logs.info('get config compose')

        config_compose = compose.RegistryCompose()
        config_compose.registry_type = const.REGISTRY_TYPE_FILE
        config_compose.dir = self._conf_dir
        return config_compose

    def _get_secret_compose(self) -> compose.RegistryCompose:
        logs.info('get secret compose')

        secret_compose = compose.RegistryCompose()
        secret_compose.registry_type = const.REGISTRY_TYPE_SECRET
        if self._secret_conf is not None and 'root' in self._secret_conf:
            secret_compose.dir = self._secret_conf['root']
        else:
            secret_compose.dir = self._scripts_dir
        return secret_compose

    def _get_artifact_compose(self) -> compose.RegistryCompose:
        logs.info('get binary compose')

        artifact_compose = compose.RegistryCompose()
        artifact_compose.registry_type = const.REGISTRY_TYPE_FILE
        artifact_compose.dir = self._artifact_dir
        return artifact_compose

    def _get_binary_compose(self) -> compose.RegistryCompose:
        logs.info('get binary compose')

        binary_compose = compose.RegistryCompose()
        binary_compose.registry_type = const.REGISTRY_TYPE_FILE
        binary_compose.dir = self._bin_dir
        return binary_compose

    def _get_docker_compose(self) -> compose.DockerRegistryCompose():
        logs.info('get docker compose')

        docker_compose = compose.DockerRegistryCompose()
        docker_compose.registry = self._deploy_config.docker_registry
        docker_compose.username = const.DOCKER_USERNAME
        docker_compose.password = const.DOCKER_PASSWORD
        return docker_compose

    def _get_svc_etcd_compose(self) -> compose.SvcEtcdCompose():
        logs.info('get svc etd compose')

        etcd_compose = compose.SvcEtcdCompose()
        if self.is_ultra:
            etcd_compose.enable = const.ETCD_ENABLE
            etcd_compose.username = const.ETCD_USERNAME
            etcd_compose.password = const.ETCD_PASSWORD
            etcd_compose.timeout = const.ETCD_TIMEOUT
            etcd_compose.endpoints = [v.ip + ':' + v.port for v in self.etcd_cluster]
        return etcd_compose

    def _get_svc_meta_compose(self) -> Dict[str, Any]:
        logs.info('get svc meta compose')

        return {
            'config_service.chain_config.chain_default.metric.cetina.enable_pamir_cetina': True,
            'config_service.chain_config.chain_default.metric.cetina.pamir_cetina_instance_name': '{}_storage'.format(
                self.domain_label)
        }

    def _get_cluster_etcd_compose(self, idx: int, etcd_config: config.EtcdConfig) -> compose.ServiceCompose:
        logs.info('get cluster etcd compose')

        etcd_compose = compose.ServiceCompose()
        etcd_compose.service = const.SERVICE_ETCD
        etcd_compose.ip = etcd_config.ip
        # etcd_compose.deploy_dir = os.path.join(self.domain_dir, const.SERVICE_ETCD + str(idx))
        etcd_compose.conf_file = '../conf/etcd.conf'
        return etcd_compose

    def _get_cluster_storage_compose(self, idx: int, storage_config: config.StorageConfig) -> compose.ServiceCompose:
        logs.info('get cluster storage compose')

        storage_compose = compose.ServiceCompose()
        storage_compose.service = const.SERVICE_STORAGE
        storage_compose.ip = storage_config.ip
        # storage_compose.deploy_dir = os.path.join(self.domain_dir, const.SERVICE_STORAGE + str(idx))
        storage_compose.conf_file = '../conf/svc.conf'
        return storage_compose

    # service must in __service_enum, service_config must has [ip, rpc_port]
    def _get_cluster_service_compose(self, service: str, idx: int, service_config: Any) -> compose.ServiceCompose:
        logs.info('get cluster {}{} compose'.format(service, idx))

        service_compose = compose.ServiceCompose()
        service_compose.service = service
        service_compose.ip = service_config.ip

        launch_conf = self._tpl_factory.get_launch_tpl()
        if service in [const.SERVICE_PORTAL, const.SERVICE_LIGHT]:
            client_ports = [('tls', service_config.client_tcp_port), ('https', service_config.client_http_port), ('ws', service_config.client_ws_port), ('wss', service_config.client_wss_port)]
            client_urls = ['{}://{}:{}'.format(schema, const.SERVER_IP, port) for schema, port in client_ports if port > 0]

            launch_conf.config.update({
                'service': {
                    'endpoint': ','.join(client_urls),
                },
                'secret': {
                    'certs_uri': 'etcd://{}/portal/certs'.format(self.chain_id)
                }
            })
        if service in [const.SERVICE_DOG, const.SERVICE_LIGHT]:
            launch_conf.config['p2p'] = {
                'host': service_config.ip,
                'port': service_config.domain_port
            }
        launch_data = schema.LaunchConfigSchema().dump(launch_conf)
        # delete launch tmpl placeholder
        launch_data.pop('init_config')
        #  if launch_data['parameters'] is not None:
           #  launch_data['parameters'].pop('/SetEnv/' + const.ENV_POD_HOST)
           #  launch_data['parameters'].pop('/SetEnv/' + const.ENV_POD_PORT)
           #  launch_data['parameters'].pop('/SetEnv/' + const.ENV_POD_NAME)
           #  launch_data['parameters'].pop('/SetEnv/' + const.ENV_POD_UUID)
           #  launch_data['parameters'].pop('/SetEnv/' + const.ENV_PARTITION_LIST)
        service_compose.conf = launch_data
        service_compose.conf_file = '../conf/launch.conf'

        env = self._tpl_factory.get_env_tpl()
        #  env[const.ENV_POD_HOST] = service_config.ip
        #  env[const.ENV_POD_PORT] = str(service_config.rpc_port)
        #  env[const.ENV_POD_NAME] = service

        # TODO support global env
        if service in [const.SERVICE_DOG, const.SERVICE_LIGHT]:
            env['DOMAIN_LISTEN_URLS0'] = f'tcp://{service_config.ip}:{service_config.domain_port}'
            env['DOMAIN_LISTEN_URLS1'] = f'tcp://{service_config.ip}:{service_config.domain_port + 1}'
            env['DOMAIN_LISTEN_URLS2'] = f'tcp://{service_config.ip}:{service_config.domain_port + 2}'
        if service in [const.SERVICE_PORTAL, const.SERVICE_LIGHT]:
            client_ports = [('tls', service_config.client_tcp_port), ('https', service_config.client_http_port), ('ws', service_config.client_ws_port), ('wss', service_config.client_wss_port)]
            client_urls = ['{}://{}:{}'.format(schema, const.SERVER_IP, port) for schema, port in client_ports if port > 0]
            env['CLIENT_LISTEN_URLS'] = ','.join(client_urls)

        env['ASAN_OPTIONS'] = ':'.join([k + '=' + v for k, v in const.TPL_ASAN_OPS.items()])
        env[const.ENV_POD_UUID] = self.gen_service_id(service, idx)
        env[service.upper() + '_ID'] = str(idx)
        env[service.upper() + '_RPC_LISTEN_URL'] = f'tcp:0.0.0.0:{service_config.rpc_port}'
        env[service.upper() + '_RPC_ADVERTISE_URL'] = f'tcp:{service_config.ip}:{service_config.rpc_port}'
        if service in [const.SERVICE_TXPOOL, const.SERVICE_LIGHT]:
            partition_beg = self.partition_size * idx
            partition_end = partition_beg + self.partition_size - 1
            env[const.ENV_PARTITION_LIST] = '{}-{}'.format(partition_beg, partition_end)
        service_compose.env = env

        return service_compose

    def _get_cluster_compose(self) -> Dict[str, compose.ServiceCompose]:
        logs.info('get cluster compose')

        cluster = {}
        if self.is_ultra:
            # self._tpl_factory.update_config_etcd(const.TPL_ETCD_API_VERSION, [v.client_url for v in self.etcd_cluster])

            for idx, etcd_config in enumerate(self._deploy_config.ultra.etcd):
                etcd_compose = self._get_cluster_etcd_compose(idx, etcd_config)
                cluster[etcd_compose.service + str(idx)] = etcd_compose

            for idx, storage_config in enumerate(self._deploy_config.ultra.storage):
                storage_compose = self._get_cluster_storage_compose(idx, storage_config)
                cluster[storage_compose.service + str(idx)] = storage_compose

            for idx, portal_config in enumerate(self._deploy_config.ultra.portal):
                portal_compose = self._get_cluster_service_compose(const.SERVICE_PORTAL, idx, portal_config)
                cluster[portal_compose.service + str(idx)] = portal_compose

            for idx, dog_config in enumerate(self._deploy_config.ultra.dog):
                dog_compose = self._get_cluster_service_compose(const.SERVICE_DOG, idx, dog_config)
                cluster[dog_compose.service + str(idx)] = dog_compose

            for idx, txpool_config in enumerate(self._deploy_config.ultra.txpool):
                txpool_compose = self._get_cluster_service_compose(const.SERVICE_TXPOOL, idx, txpool_config)
                cluster[txpool_compose.service + str(idx)] = txpool_compose

            for idx, controller_config in enumerate(self._deploy_config.ultra.controller):
                controller_compose = self._get_cluster_service_compose(const.SERVICE_CONTROLLER, idx, controller_config)
                cluster[controller_compose.service + str(idx)] = controller_compose

            for idx, compute_config in enumerate(self._deploy_config.ultra.compute):
                compute_compose = self._get_cluster_service_compose(const.SERVICE_COMPUTE, idx, compute_config)
                cluster[compute_compose.service + str(idx)] = compute_compose
        else:
            light_compose = self._get_cluster_service_compose(const.SERVICE_LIGHT, 0, self._deploy_config.light)
            cluster[light_compose.service] = light_compose

        return cluster

    def _get_meta_compose(self, cluster :Dict[str, compose.ServiceCompose]) -> Dict[str, Any]:
        logs.info('get meta compose')

        meta = {
            # '/{}/portal/certs'.format(self.chain_id): {
            #     'ca.crt': '{$secret.client.ca_cert_file}',
            #     'server.crt': '{$secret.client.cert_file}',
            #     'server.key': '{$secret.client.key_file}'
            # },
            '/{}/secrets/domain.key'.format(self.chain_id): {
                'domain_key': '{$secret.domain.key_file}'
            },
            '/{}/global/config'.format(self.chain_id): '{$config.global}',
            '/{}/services/portal/config'.format(self.chain_id): '{$config.portal}',
            '/{}/services/dog/config'.format(self.chain_id): '{$config.dog}',
            '/{}/services/txpool/config'.format(self.chain_id): '{$config.txpool}',
            '/{}/services/controller/config'.format(self.chain_id): '{$config.controller}',
            '/{}/services/compute/config'.format(self.chain_id): '{$config.compute}'
        }

        for service_name, service_compose in cluster.items():
            conf = service_compose.conf
            if conf is None:
                continue
            uuid = self.get_service_id(service_name)
            meta['/{}/services/{}/instance_config/{}'.format(self.chain_id, service_compose.service, uuid)] = conf
            service_compose.conf = None
            service_compose.conf_file = ''

        return meta

    def _get_compose(self) -> compose.DomainCompose:
        """
        Get domain compose by deploy config
        :return domain compose
        """

        logs.info('get compose')

        domain_compose = compose.DomainCompose()

        domain_compose.chain_id = self._deploy_config.chain_id
        genesis_conf = utils.get_abs_path(self._scripts_dir, self._deploy_config.genesis_conf)
        # todo check genesis_conf exists
        domain_compose.genesis_conf = genesis_conf
        domain_compose.domain_label = self._deploy_config.domain_label
        domain_compose.version = self._deploy_config.version

        domain_compose.config = self._get_config_compose()
        domain_compose.secret = self._get_secret_compose()
        domain_compose.artifact = self._get_artifact_compose()
        domain_compose.binary = self._get_binary_compose()
        domain_compose.docker = self._get_docker_compose()

        cluster = self._get_cluster_compose()
        domain_compose.meta = self._get_meta_compose(cluster)
        domain_compose.cluster = cluster

        domain_compose.run_user = self.run_user
        domain_compose.docker_mode = self._deploy_config.docker_mode
        domain_compose.light_mode = not self.is_ultra
        domain_compose.deploy_dir = self.domain_dir

        return domain_compose

    def generate_domain_compose(self) -> str:
        """
        Generate domain compose file by deploy config
        :return domain compose
        """

        domain_compose = self._get_compose()
        domain_data = schema.DomainComposeSchema().dump(domain_compose)
        domain_compose_path = os.path.join(self._scripts_dir, self.domain_label + '.json')
        utils.dump_file(domain_data, domain_compose_path)

        logs.info('dump domain_compose_path at {}'.format(domain_compose_path))

        return domain_compose_path

    def generate_secret_config(self) -> str:
        """
        Generate .secret file by deploy config with secret key
        :return .secret file path
        """

        secret_data = schema.SecretConfigSchema().dump(self._deploy_config.secret)
        secret_conf = {
            'root': self._scripts_dir,
            'file_handler': 'base64',
            'passwd_handler': '',
            'data': secret_data
        }

        secret_conf_path = os.path.join(self._scripts_dir, '.secret')
        utils.dump_file(secret_conf, secret_conf_path)
        return secret_conf_path

    def update_svc_env(self) -> str:
        """
        Update env.json at svc shells run root by deploy config
        :return env file path
        """

        logs.info('update env.json at {}'.format(self._svc_run_dir))

        svc_env = {
            'env.{}'.format(self.domain_label): {
                'type': 'chain_cluster' if self.is_ultra else 'mono',
                'nodes': {k: v.as_dict() for k, v in self.storage_nodes.items()},
                'etcd': {'cluster': [v.as_dict() for v in self.etcd_cluster]}
            }
        }

        return svc.update_svc_env(self._svc_run_dir, svc_env)
