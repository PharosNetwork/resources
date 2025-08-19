#!/usr/bin/env python3
# coding=utf-8
from typing import List


class Context(object):
    job: str = ''
    branch: str = ''
    repo: str = ''
    user: str = ''
    workspace: str = ''
    pipeline_id: str = ''
    iplist: List[str] = ['127.0.0.1']
    deploy_mode: str = 'ultra'
    run_user: str = 'root'
    passwd: str = 'mychain123'
    port = 18000
    http_port = 18100
    wss_port = 18200
