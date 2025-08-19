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
from pharos_ops.toolkit import logs

import os
import json
import shutil
import subprocess
import jsbeautifier
from typing import Dict, Any, Callable, Optional


def exec_run(shell_name: str, **kwargs) -> int:
    """
    Execute shell command.
    :param shell_name: name of shell command.
    :param kwargs: parameters of shell command.
    :return execute result code
    """
    logs.debug('exec: ' + shell_name)
    run_process = subprocess.run(shell_name, shell=True, **kwargs)
    ret_code = run_process.returncode
    return ret_code


# assert(exec_run)
def must_exec_run(shell_name: str, **kwargs):
    if exec_run(shell_name, **kwargs) != 0:
        logs.fatal('failed to exec run, shell = "{}", cwd = {}'.format(shell_name, os.getcwd()))


# assert(os.path.exists)
def must_path_exists(path: str):
    if not os.path.exists(path):
        logs.fatal('path is not exists, path = {}'.format(path))


def load_file(file_path: str) -> Dict[str, Any]:
    """
    Load file as json.
    :param file_path: path of file.
    :return file content as json
    :raise Exception
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def dump_file(data: Dict[str, Any], output_file_path: str):
    """
    Dump file with json.
    :param data: file content as json
    :param output_file_path file path to dump
    :raise Exception
    """
    with open(output_file_path, 'w', encoding='utf8') as output_file:
        json.dump(data, output_file, indent=2)


def get_abs_path(root: str, path: str) -> str:
    """
    Get absolute path
    :param root: root to as relative path base
    :param path: path
    """
    if not os.path.isabs(path):
        return os.path.abspath(os.path.join(root, path))
    return path


def parse_url(url: str, default_schema: str = 'http') -> (str, str, int):
    """
    Parse url like 'schema://hostname:port, //hostname:port, hostname:port'
    :param url: origin url
    :param default_schema: default schema if not parsed
    :return: url(scheme, hostname, port)
    """
    i = url.find('//')
    prefix = ''
    if i < 0:
        prefix = default_schema + '://'
    elif i == 0:
        prefix = default_schema + ':'
    import urllib.parse
    u = urllib.parse.urlparse(prefix + url)
    if not u.netloc:
        logs.fatal('url: {} is invalid'.format(url))
    return u.scheme, u.hostname, u.port


def get_tid() -> str:
    """
    Get uuid with timestamp
    """
    import datetime
    return '{0:%Y%m%d_%H%M%S_%f}'.format(datetime.datetime.now())


def update_dict_keys(d: Dict, k: str, v: Any):
    """
    Update dict with keys like 'a.b.c'
    :param d: dict
    :param k: multi key
    :param v: value
    """
    logs.debug('update_dict_keys, key = {}, value = {}'.format(k, v))
    keys = k.split('.')
    last_key = keys[-1]
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    d[last_key] = v


def get_dict_keys_val(d: Dict, k: str) -> Any:
    """
    Get value from dict with keys like 'a.b.c'
    :param d: dict
    :param k: multi key
    :return: value
    """
    logs.debug('get_dict_keys_val, key = {}'.format(k))
    keys = k.split('.')
    last_key = keys[-1]
    for key in keys[:-1]:
        if key not in d:
            return None
        d = d[key]
    if last_key not in d:
        return None
    return d[last_key]


def replace_value(val: Any, replace_hook: Callable):
    """
    Replace value with hook function
    :param val: value
    :param replace_hook: function(str) -> Any
    """
    if isinstance(val, str):
        return replace_hook(val)
    if isinstance(val, dict):
        for k in val:
            val[k] = replace_value(val[k], replace_hook)
        return val
    elif isinstance(val, list):
        for i in range(len(val)):
            val[i] = replace_value(val[i], replace_hook)
        return val
    return val


def load_json(file: str):
    with open(file, 'r') as fh:
        return json.load(fh)

def dump_json(file: str, data: Dict[str, Any], list_inline: bool=False):
    if list_inline:
        options = jsbeautifier.default_options()
        options.indent_size = 2
        with open(file, 'w') as fh:
            fh.write(jsbeautifier.beautify(json.dumps(data), options))
    else:
        with open(file, 'w') as fh:
            json.dump(data, fh, indent=2)

def clean_local_folder(folder: str, except_: str=''):
   if not os.path.exists(folder):
       return
   logs.debug(f'clean_folder: {folder}, except: {except_}')
   for file in os.scandir(folder):
       if not except_ or not file.path.endswith(except_):
           try:
               shutil.rmtree(file.path)
           except OSError:
               os.remove(file.path)

def to_serializable(obj):
    if isinstance(obj, dict):
        return {key: to_serializable(value) for key, value in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {key: to_serializable(value) for key, value in vars(obj).items()}
    elif isinstance(obj, list):
        return [to_serializable(item) for item in obj]
    elif isinstance(obj, (int, float, str, bool)):
        return obj
    elif obj is None:
        return obj
    else:
        raise TypeError(f"Type {type(obj)} not serializable")

def safe_get_nested(data: dict, *keys: Any) -> Optional[Any]:
    try:
        for key in keys:
            data = data[key]
            if data is None:
                return None
    except (KeyError, TypeError):
        return None
    return data