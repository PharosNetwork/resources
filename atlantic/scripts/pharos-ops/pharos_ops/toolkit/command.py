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
import os

from typing import List, Dict, Any


def test_mkdir(*ds: List[str]) -> str:
    d = os.path.join(*ds)
    return 'test -d {0} || mkdir -p {0}'.format(d)


def test_rmdir(d: str):
    return 'test -d {0} && rm -rf {0}'.format(d)


def find_name(d: str, f: str) -> str:
    return "find {} -name '{}'".format(d, f)


def cd_execs(d: str, *cmds: List[str]) -> str:
    commands = ['cd ' + d]
    commands.extend(cmds)
    return ' && '.join(commands)


def ln_sf(s: str, t: str):
    return 'ln -sf {} {}'.format(s, t)


def rm_f(f: str):
    return 'rm -f {}'.format(f)


def rmdir_rf(d: str):
    return 'rm -rf {}'.format(d)


def cp_a(s: str, t: str):
    return 'cp -a {} {}'.format(s, t)


def cpdir_a(s: str, t: str):
    return 'cp -ra {} {}'.format(s, t)


def echo_write(d: Dict[str, Any], p: str):
    return "echo '{}' > {}".format(d, p)


def ps_ef(s: str) -> str:
    commands = ['ps -ef', "grep -E '{}'".format(s), 'grep -v grep']
    return ' | '.join(commands)


def pspid_greps(s: str, *cmds: List[str]) -> str:
    commands = ['ps -eo pid,cmd', "grep '{}'".format(s)]
    commands.extend(cmds)
    return ' | '.join(commands)

def export(k: str, v: str) -> str:
    return "export {}='{}'".format(k, v)

def ulimit(core_limit: str) -> str:
    return 'ulimit -c ' + core_limit
