#!/usr/bin/env python3
# coding=utf-8
from aldaba_ops.toolkit import utils, connect, entrance, logs
from aldaba_ops.test_runner import context, utils as myutils

import os
import time
import re
import glob


def prepare_ssh(ctx: context.Context):
    logs.debug('######## prepare ssh ########')
    
    l_pub = os.path.join(os.path.expanduser("~/.ssh"), "id_rsa.pub")
    pub_key = open(l_pub).read().strip()
    print('pub_key', pub_key)
    for ip in ctx.iplist:
        print('connect', ip, ctx.run_user, ctx.passwd)
        with connect.Connection(host=ip, user=ctx.run_user, pwd=ctx.passwd) as conn:
            conn.run('echo "%s" >> /root/.ssh/authorized_keys' % pub_key)
        

def prepare_aldaba(ctx: context.Context):
    logs.debug('######## prepare aldaba ########')
    
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


def prepare_systest(ctx: context.Context):
    logs.debug('######## prepare systest ########')

    systest = os.path.join(ctx.workspace, 'systest')
    os.chdir(systest)

    systest_mychain = "data_prod/mychain.json"
    chain_dict = utils.load_file(systest_mychain)
    chain_dict["host"] = ctx.iplist[0]
    chain_dict['port'] = ctx.wss_port # hardcode
    chain_dict['httpPort'] = ctx.http_port # hardcode
    chain_dict['protocol'] = 'WEBSOCKET'
    chain_dict["serialRun"] = 'data_prod/2.1.1'
    backups = ''
    if len(ctx.iplist) > 1:
        backups = ",".join([ip + ':' + str(ctx.port + idx) for idx, ip in enumerate(ctx.iplist) if idx > 0])
    chain_dict['backupNodes'] = backups
    print(chain_dict)
    utils.dump_file(chain_dict, systest_mychain)

    systest_properties = "data_prod/properties.json"
    prop_dict = utils.load_file(systest_properties)
    prop_dict["sys_ip"] = ctx.iplist[0]
    prop_dict['sys_port'] = ctx.port
    prop_dict["sys_remote_user"] = ctx.run_user
    prop_dict["sys_remote_password"] = ctx.passwd
    print(prop_dict)
    utils.dump_file(prop_dict, systest_properties)


def collect_logs(ctx: context.Context):
    logs.debug('######## collect logs ########')

    for idx, ip in enumerate(ctx.iplist):
        print('connect', ip, ctx.run_user, ctx.passwd)
        with connect.Connection(host=ip, user=ctx.run_user, pwd=ctx.passwd) as conn:
            try:
                conn.run(f'find /tmp/aldaba-ng/ -name "log"| xargs tar czvf /tmp/aldaba-ng/domain{idx}_log.tgz')
                conn.get(f'/tmp/aldaba-ng/domain{idx}_log.tgz', f'{ctx.workspace}/domain{idx}_log.tgz')
            except Exception as e:
                logs.warn('{}'.format(e))


def handle_report(ctx: context.Context):
    print('######## handle report ########')

    systest = os.path.join(ctx.workspace, 'systest')
    os.chdir(systest)

    ignore = []
    result = []
    check = {}
    fn = 'report.csv'
    with open(fn, "r", encoding="utf-8") as fd:
        t_case = 0
        f_case = 0
        for l in fd.readlines():
            if not l.startswith('"'):
                continue
            ss = l.split(",")
            f_path = ss[1].strip('"')
            # fn = os.path.basename(f_path)
            p = re.compile(r'\"(.*?)\"')
            findstr = p.findall(l)
            name = findstr[0]
            if '"true"' in l:
                t_case += 1
                check[(f_path, name)] = True
            if '"false"' in l:
                if not check.get((f_path, name)):
                    check[(f_path, name)] = False
                    f_case += 1
                    result.append(l)

        print("The total case count: " + str(t_case + f_case))
        print("The pass case count: " + str(t_case))
        print("The pass rate: " + str(t_case / (t_case + f_case)))
        print("The fail case count: " + str(f_case))
    print("The fail case : ")
    ret = 0
    for l in result:
        if not l.startswith('"'):
            continue
        ss = l.split(",")
        f_path = ss[1].strip('"')
        rel_name = os.path.relpath(f_path, systest)
        _, log = myutils.exec_no_print("git log -n 1 " + rel_name)
        fn = os.path.basename(f_path)
        p = re.compile(r'\"(.*?)\"')
        findstr = p.findall(l)
        name = findstr[0]
        if (fn, name) in ignore or check[(f_path, name)]:
            continue
        else:
            print(l)
            print(log)
            ret = 1

    systest_log_dir = os.path.join(systest, 'log')
    for f in glob.glob("*.result"):
        myutils.mycp(f, os.path.join(systest_log_dir, f))
    target_csv = os.path.join(systest_log_dir, ctx.pipeline_id + "-" + ctx.job + "-report.csv")
    myutils.mycp("report.csv", target_csv)
    tar_name = "systest_{}.tar.gz".format(ctx.job)
    myutils.tar_dir(tar_name, ["log"], "w:gz")
    print('tar done at {}: {}'.format(systest, os.listdir(systest)))
    myutils.upload_log(target_csv, ctx.pipeline_id + "/")

    return ret


def run_aldaba():
    print('######## run aldaba ########')

    workspace = os.getenv('WORKSPACE', '')
    os.chdir(os.path.join(workspace, 'scripts'))

    domain_list = [domain.strip() for domain in open('domain_list').read().split(" ") if len(domain) > 0]
    entrance.deploy(domain_list, None)
    entrance.bootstrap(domain_list)
    entrance.start(domain_list, None, '')


def stop_aldaba():
    print('######## stop aldaba ########')

    workspace = os.getenv('WORKSPACE', '')
    os.chdir(os.path.join(workspace, 'scripts'))

    domain_list = [domain.strip() for domain in open('domain_list').read().split(" ") if len(domain) > 0]
    entrance.stop(domain_list, None)


def run_systest():
    print('######## run systest ########')

    workspace = os.getenv('WORKSPACE', '')
    os.chdir(os.path.join(workspace, 'systest'))

    systest_mychain = "data_prod/mychain.json"
    systest_properties = "data_prod/properties.json"
    asset_conf = 'data_prod/2.1.1'

    cmd = """java -cp "target/lib" \
                    -jar "target/aldaba-test-framework-1.0-SNAPSHOT.jar" \
                    -n "{}" \
                    -p "{}" \
                    -t "{}" \
                    | tee test_system.result
                    """.format(systest_mychain,
                               systest_properties,
                               asset_conf)
    utils.exec_run(cmd)


def run():
    run_aldaba()
    time.sleep(30)
    run_systest()
    time.sleep(30)
    stop_aldaba()
    return 0
