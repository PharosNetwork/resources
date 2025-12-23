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
def generate(deploy_file: str):
    """
    Command: pharos-ops configure
    """

    generator = conf.Generator(deploy_file)
    generator.run()


@catch_exception
def deploy(domain_files: str, service: str):
    """
    Command: pharos-ops deploy
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    if len(domain_files) == 1:
        composer = core.Composer(domain_files[0])
        composer.deploy(service)
    else:
        procs = []
        for domain_file in domain_files:
            composer = core.Composer(domain_file)
            p = Process(target=composer.deploy, args=(service,))
            procs.append(p)
            p.start()
        for p in procs:
            p.join()
            

@catch_exception
def update(domain_files: str, service: str):
    """
    Command: pharos-ops deploy
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    if len(domain_files) == 1:
        composer = core.Composer(domain_files[0])
        composer.update(service)
    else:
        procs = []
        for domain_file in domain_files:
            composer = core.Composer(domain_file)
            p = Process(target=composer.update, args=(service,))
            procs.append(p)
            p.start()
        for p in procs:
            p.join()
            
            
@catch_exception
def update_conf(domain_files: str, service: str):
    """
    Command: pharos-ops deploy
    """
    # TODO 多domain_files部署的时候，确保所有domain_files的chain_id/genesis.conf一致, domain_label不冲突
    if len(domain_files) == 1:
        composer = core.Composer(domain_files[0])
        composer.update_conf(service)
    else:
        procs = []
        for domain_file in domain_files:
            composer = core.Composer(domain_file)
            p = Process(target=composer.update_conf, args=(service,))
            procs.append(p)
            p.start()
        for p in procs:
            p.join()
            
            
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
def add_validator(endpoint, key, no_prefix, domains):
    """
    Command: pharos-ops add-validator
    """
    for domain in domains:
        composer = core.Composer(domain)
        composer.add_validator(endpoint, key, no_prefix)
    

@catch_exception
def exit_validator(endpoint, key, no_prefix, domains):
    """
    Command: pharos-ops exit-validator
    """
    
    for domain in domains:
        compose = core.Composer(domain)
        compose.exit_validator(endpoint, key, no_prefix)
        
@catch_exception
def remove_validator_prefix(endpoint, key, domains):
    """
    Command: pharos-ops remove-validator-prefix
    """
    
    for domain in domains:
        composer = core.Composer(domain)        
        compose.exit_validator(endpoint, key, False)
        compose.add_validator(endpoint, key, True)    

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
