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
from pharos_ops.toolkit import utils, logs

import subprocess

from typing import List
import fabric


def _su_local_user(user: str, pwd: str):
    """
    Checkout local user if necessary
    :param user: user to checkout
    :param pwd: password
    """

    run_process = subprocess.run('whoami', shell=True, stdout=subprocess.PIPE)
    cur_user = run_process.stdout.decode().strip()
    if cur_user == user:
        return
    logs.warn('current user {} is not run user {}'.format(cur_user, user))
    # with subprocess.Popen('su {}'.format(user), shell=True, stdin=subprocess.PIPE) as p:
    #     p.stdin.write(pwd.encode('utf-8'))
    #     p.stdin.write('\n'.encode('utf-8'))


class Connection(object):
    """Wrapper for underlying connections whether local or remote."""

    _host: str
    _user: str
    _pwd: str

    _conn: fabric.Connection = None

    def __init__(self, host: str, user: str, pwd: str = ''):
        self._host = host
        self._user = user
        self._pwd = pwd
        if host in ['127.0.0.1', 'localhost']:
            _su_local_user(user, pwd)
        else:
            connect_kwargs = {}
            if len(pwd):
                connect_kwargs['password'] = pwd

            self._conn = fabric.Connection(host=host, user=user, connect_kwargs=connect_kwargs)

    @property
    def user(self) -> str:
        return self._user

    @property
    def host(self) -> str:
        return self._host

    @property
    def ssh_host(self) -> str:
        return f'{self._user}@{self._host}'

    def run(self, command) -> int:
        if self._conn:
            logs.debug('run: ' + command)
            res = self._conn.run(command)
            ret_code = res.exited
        else:
            ret_code = utils.exec_run(command)
        return ret_code

    def must_run(self, command):
        ret_code = self.run(command)
        if ret_code != 0:
            logs.fatal('failed to run on {}, command = "{}"'.format(self.host, command))

    def local(self, command) -> int:
        if self._conn:
            logs.debug('local: ' + command)
            res = self._conn.local(command)
            ret_code = res.exited
        else:
            ret_code = utils.exec_run(command)
        return ret_code

    def must_local(self, command):
        ret_code = self.local(command)
        if ret_code != 0:
            logs.fatal('failed to local run, command = {}'.format(command))

    def get(self, remote: str, local: str, preserve_mode: bool = True):
        if self._conn:
            logs.debug('get: ' + remote + ' to ' + local)
            self._conn.get(remote, local, preserve_mode)
        else:
            option = '-a' if preserve_mode else ''
            shell_command = 'cp {} {} {}'.format(option, remote, local)
            utils.must_exec_run(shell_command)

    def put(self, local: str, remote: str, preserve_mode: bool = True):
        if self._conn:
            logs.debug('put: ' + local + ' to ' + remote)
            self._conn.put(local, remote, preserve_mode)
        else:
            option = '-a' if preserve_mode else ''
            shell_command = 'cp {} {} {}'.format(option, local, remote)
            utils.must_exec_run(shell_command)

    def sync(self, local: str, remote: str, rsync_opts: str = '-av'):
        if self._conn:
            logs.debug('rsync: ' + local + ' to ' + remote)
            self._conn.local(f'rsync {rsync_opts} {local} {self.ssh_host}:{remote}')
        else:
            shell_command = f'rsync {rsync_opts} {local} 127.0.0.1:{remote}'
            utils.must_exec_run(shell_command)
            
    def sync_back(self, remote: str, local: str, rsync_opts: str = '-av'):
        if self._conn:
            logs.debug('rsync: ' + remote + ' to ' + local)
            self._conn.local(f'rsync {rsync_opts} {self.ssh_host}:{remote} {local}')
        else:
            shell_command = f'rsync {rsync_opts} 127.0.0.1:{remote} {local}'
            utils.must_exec_run(shell_command)

    def cd_run(self, path: str, *commands: List[str]) -> int:
        if self._conn:
            with self._conn.cd(dir):
                for command in commands:
                    logs.debug('cd: ' + path, ' runs: ' + commands)
                    res = self._conn._run(command)
                    if res.exited != 0:
                        return res.exited
        else:
            cd_commands = ['cd path']
            cd_commands.extend(commands)
            shell_command = ' && '.join(cd_commands)
            return utils.exec_run(shell_command)

    def must_cd_run(self, path: str, *commands: List[str]):
        ret_code = self.cd_run(path, *command)
        if ret_code != 0:
            logs.fatal('failed to cd {} run on {}, commands = {}'.format(path, self.host, commands))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self._conn:
            self._conn.close()
