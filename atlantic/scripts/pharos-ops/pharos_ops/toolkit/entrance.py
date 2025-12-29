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
from multiprocessing import Process
from functools import wraps
from typing import List

from pharos_ops.toolkit import conf, core, logs
import traceback
import subprocess
import os
from pharos_ops.toolkit.conn_group import local
import shutil
from .schemas import DeploySchema
import json

def catch_exception(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logs.error(f'{e}')
            pass
    return wrapped


@catch_exception
def generate(deploy_file: str, need_genesis: bool = False, key_passwd: str = ""):
    """
    Command: pharos-ops configure
    """

    generator = conf.Generator(deploy_file, key_passwd)
    generator.run(need_genesis)

@catch_exception
def generate_genesis(deploy_file: str):
    """
    Command: pharos-ops generate-genesis
    """
    generator = conf.Generator(deploy_file)
    generator.generate_genesis()

# Deploy, update, and update_conf functions removed
# New simplified flow: generate -> bootstrap -> start
# Management directory is now the deployment directory
            
            
@catch_exception
def clone(src_domain: str, dest_domains: List[str], is_cold: bool, backup: bool):
    """
    Command: pharos-ops clone
    """
    
    src_composer = core.Composer(src_domain)
    try:
        placement_info = src_composer.clone_from(is_cold)
        
        for dest_domain in dest_domains:
            composer = core.Composer(dest_domain)
            composer.clone_to(placement_info, backup)

    except Exception as e:
        error_msg = traceback.format_exc()
        print(error_msg)


@catch_exception
def update_validator(endpoint, key, domains, poolId, new_owner):
    """
    Command: pharos-ops update-validator
    """
    for domain in domains:
        composer = core.Composer(domain)
        composer.update_validator(endpoint, key, poolId, new_owner)


@catch_exception
def add_validator(endpoint, key, domains):
    """
    Command: pharos-ops add-validator
    """
    for domain in domains:
        composer = core.Composer(domain)
        composer.add_validator(endpoint, key)
    

@catch_exception
def exit_validator(endpoint, key, domains):
    """
    Command: pharos-ops exit-validator
    """
    
    for domain in domains:
        compose = core.Composer(domain)
        compose.exit_validator(endpoint, key)
    

@catch_exception
def clean(domain_files: str, service: str, all: bool):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.clean(service, all)


@catch_exception
def bootstrap(domain_files: str):
    """
    Command: pharos-ops bootstrap
    """
    # for domain_file in domain_files:
    #     composer = core.Composer(domain_file)
    #     composer.bootstrap()
    if len(domain_files) == 1:
        composer = core.Composer(domain_files[0])
        composer.bootstrap()
    else:
        procs = []
        for domain_file in domain_files:
            composer = core.Composer(domain_file)
            p = Process(target=composer.bootstrap)
            procs.append(p)
            p.start()
        for p in procs:
            p.join()


@catch_exception
def status(domain_files: str, service: str):
    """
    Command: pharos-ops status
    """

    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.status(service)
        
@catch_exception
def diff(domain1: str, domain2: str, start: str, statefork: bool):
    """
    Command: pharos-ops diff
    """
    composer1 = core.Composer(domain1)
    composer2 = core.Composer(domain2)
    if statefork:
        core.diffstatefork(composer1, composer2, start)
    else:
        core.diff(composer1, composer2, start)
    
@catch_exception
def query(domain, type, arg):
    composer = core.Composer(domain)
    
    if type == 'stable_block_number':
        result = composer.get_stable_block_num()
    elif type == 'written_block_number':
        result = composer.get_written_block_num()
    elif type == 'block':
        result = composer.get_block_by_num(int(arg[0], 10))
    elif type == 'block_by_hash':
        result = composer.get_block_by_hash(arg[0])
    elif type == 'tx':
        result = composer.get_tx(arg[0])
    elif type == 'receipt':
        result = composer.get_receipt(arg[0])
    elif type == 'code':
        result = composer.get_code(arg[0])
    elif type == 'nonce':
        result = composer.get_nonce(arg[0])
    elif type == 'balance':
        result = composer.get_balance(arg[0])
    else:
        logs.error(f"Unknown query type: {type}")
        return
    
    if not result is None:
        print(result)
    else:
        logs.error("Failed to query")
    

@catch_exception
def start(domain_files: str, service: str, extra_storage_args: str):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.start(service, extra_storage_args)


@catch_exception
def restart(domain_files: str, service: str, extra_storage_args: str):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.stop(service)
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.start(service, extra_storage_args)


@catch_exception
def stop(domain_files: str, service: str, force=False):
    """
    Command: pharos-ops start
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    for domain_file in domain_files:
        composer = core.Composer(domain_file)
        composer.stop(service, force)


@catch_exception
def upgrade():
    """
    Command: pharos-ops upgrade
    """
    fh = open("./deploy.light.json", "r")
    deploy_data = json.load(fh)
    deploy = DeploySchema().load(deploy_data)

    deploy_path = f"{deploy.deploy_root}"
    original_cwd = os.getcwd()
    logs.info(f"original_cwd: {original_cwd}")
    logs.info(f"deploy_path: {deploy_path}")
    files_to_remove = [
        f"{deploy_path}/domain/light/bin/libevmone.so",
        f"{deploy_path}/domain/light/bin/pharos_light",
        f"{deploy_path}/domain/light/bin/VERSION",
        f"{deploy_path}/domain/client/bin/pharos_cli",
    ]
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)

    symlinks = [
        (
            f"{original_cwd}/../bin/libevmone.so",
            f"{deploy_path}/domain/light/bin/libevmone.so",
        ),
        (
            f"{original_cwd}/../bin/pharos_light",
            f"{deploy_path}/domain/light/bin/pharos_light",
        ),
        (
            f"{original_cwd}/../bin/VERSION",
            f"{deploy_path}/domain/light/bin/VERSION",
        ),
    ]
    for src, dst in symlinks:
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(src, dst)

    try:
        # shutil.copyfile(
        #     f"{deploy_path}/domain/light/conf/monitor.conf",
        #     f"{original_cwd}/../conf/monitor.conf",
        # )

        shutil.copyfile(
            f"{original_cwd}/../bin/pharos_cli",
            f"{deploy_path}/domain/client/bin/pharos_cli",
        )
    except Exception as e:
        logs.error(f"Upgrade failed: {e}")
    finally:
        os.chdir(original_cwd)
