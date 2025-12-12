#!/usr/bin/env python3
# coding=utf-8
from pharos_ops.test_runner.schemas import flow
from pharos_ops.test_runner import context, utils as myutils
from pharos_ops.toolkit import utils, logs, connect, entrance

import os
import importlib

from subprocess import Popen, PIPE
from multiprocessing import Process, Array
from typing import Dict, List, Any, IO

RET_CODE: int = 0
STAGES: Dict[str, flow.Stage] = {}
ACTION_MODULE: Any = None
TOTAL_CASES: int = 0
PASSED_CASES: int = 0
FAILED_CASE_STAGE: str = '' 
FAILED_CASE_COMMAND: str = ''
FAILED_CASE_OUT: str = ''  


def prepare_ssh(ctx: context.Context):
    logs.debug('######## prepare ssh ########')
    
    l_pub = os.path.join(os.path.expanduser("~/.ssh"), "id_rsa.pub")
    pub_key = open(l_pub).read().strip()
    print('pub_key', pub_key)
    for ip in ctx.iplist:
        print('connect', ip, ctx.run_user, ctx.passwd)
        with connect.Connection(host=ip, user=ctx.run_user, pwd=ctx.passwd) as conn:
            conn.run('echo "%s" >> /root/.ssh/authorized_keys' % pub_key)
        

def prepare_pharos(ctx: context.Context):
    logs.debug('######## prepare pharos ########')
    
    os.chdir(os.path.join(ctx.workspace, 'scripts'))

    deploy_conf_path = 'deploy{}.{}.json'.format('.chain' if len(ctx.iplist) > 1 else '', ctx.deploy_mode)
    deploy_conf = utils.load_file(deploy_conf_path)
    deploy_conf['run_user'] = ctx.run_user
    domain_compose_paths = []
    for idx, ip in enumerate(ctx.iplist):
        domain_conf = deploy_conf['domains']
        domain_id = 'domain' + str(idx)
        if domain_id not in domain_conf:
            continue
        cluster = domain_conf[domain_id]['cluster']
        for service in cluster:
            service['ip'] = ip
        domain_compose_paths.append('domain{}.json'.format(idx))
    utils.dump_file(deploy_conf, deploy_conf_path)
    entrance.generate(deploy_conf_path)
    with open('domain_list', 'w', encoding='utf8') as output_file:
        output_file.write(' '.join(domain_compose_paths))


def collect_logs(ctx: context.Context):
    logs.debug('######## collect logs ########')

    for idx, ip in enumerate(ctx.iplist):
        print('connect', ip, ctx.run_user, ctx.passwd)
        with connect.Connection(host=ip, user=ctx.run_user, pwd=ctx.passwd) as conn:
            try:
                conn.run(f'find /tmp/pharos-node/ -name "log"| xargs tar czvf /tmp/pharos-node/domain{idx}_log.tgz')
                conn.get(f'/tmp/pharos-node/domain{idx}_log.tgz', f'{ctx.workspace}/domain{idx}_log.tgz')
            except Exception as e:
                logs.warn('{}'.format(e))

def execute_shell(command: str, args: List[str] = []):
    logs.debug(f'execute shell, command={command}, args={args}')

    proc = Popen(command, *args, shell=True, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()
    retcode = proc.returncode
    if retcode != 0:
        err_str = err.decode('utf-8')
        if len(err_str) > 0:
            ogs.error(err_str)
        logs.error(f'failed execute shell, command={command}, args={args}, retcode={retcode}')
        return err_str, False
    out_str = out.decode('utf-8')
    if len(out_str) > 0:
        logs.info(out_str)
    return out_str, True


def execute_assert(input: str, fassert: flow.Assert):
    if fassert.action == '':
        return True
    logs.debug(f'execute assert, input={input}, assert={fassert.action}, expect={fassert.expect}')

    func = getattr(ACTION_MODULE, fassert.action)
    try:
        output = func(input)
        if fassert.expect != output:
            logs.error(f'failed execute assert, assert={fassert.action}, expect={fassert.expect}, actually={output}')
            return False
    except Exception as e:
        logs.error(f'failed execute assert, err = {e}, assert={fassert.action}')
        return False
    return True


def import_action_scripts(root_dir: str, scripts_path: str):
    logs.debug(f'import action scripts, path={scripts_path}')

    import shutil
    file_path = os.path.abspath(__file__)
    scripts_path = utils.get_abs_path(root_dir, scripts_path)
    shutil.copyfile(scripts_path, os.path.dirname(file_path) + '/action.py')
    global ACTION_MODULE
    ACTION_MODULE = importlib.import_module('pharos_ops.test_runner.action')


def export_envs(envs: Dict[str, str]):
    logs.debug(f'export envs, envs={envs}')

    for k, v in envs.items():
        os.environ[k] = v


def update_stage(root_dir: str, stage: flow.Stage):
    if len(stage.template) == 0:
        return
    tpl_path = utils.get_abs_path(root_dir, stage.template)
    tpl_data = utils.load_file(tpl_path)
    stage_tpl = flow.StageSchema().load(tpl_data)
    if stage.workspace == '':
        stage.workspace = stage_tpl.workspace
    if stage.pre.command == '':
        stage.pre = stage_tpl.pre
    if stage.post.command == '':
        stage.post = stage_tpl.post
    if stage.runs_type == '':
        stage.runs_type = stage_tpl.runs_type
    if len(stage.runs) == 0:
        stage.runs = stage_tpl.runs


def orchestrate_flow(root_dir: str, flow_inst: flow.Flow):
    logs.debug(f'orchestrate flow, flow_inst={flow_inst}')

    first_stage = flow_inst.stages[0].name
    last_stage = flow_inst.stages[-1].name
    stages = {stage.name: stage  for stage in flow_inst.stages}
    global TOTAL_CASES
    for idx, stage in enumerate(flow_inst.stages):
        update_stage(root_dir, stage)
        if stage.pre.command != '':
            TOTAL_CASES += 1
        if stage.post.command != '':
            TOTAL_CASES += 1
        for run in stage.runs:
            if run.command != '':
                TOTAL_CASES += 1
        if not stage.end:
            if idx < len(flow_inst.stages) - 1:
                if stage.next == '':
                    stage.next = flow_inst.stages[idx+1].name
                else:
                    assert(stage.next in stages)
                if stage.error == '':
                    stage.error = last_stage
                else:
                    assert(stage.error in stages)
            else:
                if stage.next == '' or stage.error == '':
                    stage.end = True
        else:
            stage.next = ''
            stage.error = ''
    if flow_inst.start_stage == '':
        flow_inst.start_stage = first_stage
    else:
        assert(flow_inst.start_stage in stages)
    global STAGES
    STAGES.update(stages)
    # logs.info(f'orchestrate flow completed, stages={stages}, start_stage={flow_inst.start_stage}')


def execute_command(command: flow.Command, workspace: str = ''):
    if command.command == '':
        return True
    logs.info(f'execute command, command={command.command}, args={command.args}, asserts_len={len(command.asserts)}')

    shell_cmd =  command.command
    if len(workspace) > 0:
        shell_cmd = f'cd {workspace} && {shell_cmd}'
    output, res = execute_shell(shell_cmd, command.args)
    global FAILED_CASE_COMMAND
    global FAILED_CASE_OUT
    if not res:
        FAILED_CASE_COMMAND = command
        FAILED_CASE_OUT = output
        logs.error(f'failed execute command on error, command={command.command}, args={command.args}')
        return False
    for fassert in command.asserts:
        if not execute_assert(output, fassert):
            FAILED_CASE_COMMAND = command
            FAILED_CASE_OUT = output
            logs.error(f'failed execute command on assert, command={command.command}, args={command.args}')
            return False
    global PASSED_CASES
    PASSED_CASES += 1
    return True


def async_execute_command(command: flow.Command, idx: int, arr: Array, workspace: str = ''):
    logs.debug(f'async execute command, command={command.command}, args={command.args}, idx={idx}')
               
    res = execute_command(command, workspace)
    arr[idx] = res


def async_execute_commands(commands: List[flow.Command], workspace: str = ''):
    logs.debug(f'async execute commands, commands_len={len(commands)}')

    arr = Array('b', len(commands))
    procs = []
    for idx, command in enumerate(commands):
        p = Process(target=async_execute_command, args=(command, idx, arr, workspace,))
        procs.append(p)
        p.start()
    for p in procs:
        p.join()
    for idx, res in enumerate(arr):
        if not res:
            return False
    return True


def execute_commands(commands: List[flow.Command], parallel: bool = False, workspace: str = ''):
    logs.info(f'execute commands, commands_len={len(commands)}, parallel={parallel}')

    if parallel:
        return async_execute_commands(commands, workspace)
    for command in commands:
        if not execute_command(command, workspace):
            return False
    return True


def must_execute_command(command: flow.Command, workspace: str = ''):
    if not execute_command(command, workspace):
        logs.fatal('failed to execute command: ' + command.command)


def must_execute_commands(commands: List[flow.Command], parallel: bool = False, workspace: str = ''):
    if not execute_commands(commands, parallel, workspace):
        logs.fatal('failed to execute commands')


def run_stage(current_stage_name: str):
    if current_stage_name == '':
        return
    current_stage = STAGES[current_stage_name]
    logs.info(f'======== running: {current_stage_name} ========')
    logs.info(f'DESCRIPTION: {current_stage.description}')
    try:
        must_execute_command(current_stage.pre, current_stage.workspace)
        must_execute_commands(current_stage.runs, current_stage.runs_type == 'parallel', current_stage.workspace)
        must_execute_command(current_stage.post, current_stage.workspace)
        current_stage_name = current_stage.next
    except Exception as e:
        global FAILED_CASE_STAGE
        FAILED_CASE_STAGE = current_stage_name
        current_stage_name = current_stage.error
        global RET_CODE
        RET_CODE = 1
    finally:
        if not current_stage.end:
            run_stage(current_stage_name)
        else:
            logs.info(f'========run completed, result={RET_CODE}========')


def run(file_path: str):
    file_data = utils.load_file(file_path)
    flow_inst = flow.FlowSchema().load(file_data)
    root_dir = os.path.dirname(file_path)
    import_action_scripts(root_dir, flow_inst.action_scripts)
    export_envs(flow_inst.envs)
    orchestrate_flow(root_dir, flow_inst)
    run_stage(flow_inst.start_stage)
    logs.echo(f'TOTAL_CASES: {TOTAL_CASES}')
    logs.echo(f'PASSED_CASES: {PASSED_CASES}')
    if RET_CODE != 0:
        logs.echo(f'FAILED_CASE: {FAILED_CASE_STAGE}.{FAILED_CASE_COMMAND}')
        logs.echo(FAILED_CASE_OUT)
    return RET_CODE