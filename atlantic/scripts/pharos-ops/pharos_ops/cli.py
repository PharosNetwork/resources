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
from pharos_ops.toolkit import entrance, logs
from pharos_ops.test_runner import bvt, systest, context

import os
import sys
import base64
import click
import ipaddress
import json
from .toolkit.schemas import DeploySchema


B_LOGO = b'ICBfX19fICBfICAgXyAgICBfICAgIF9fX18gICBfX18gIF9fX18gIAogfCAgXyBcfCB8IHwgfCAgLyBcICB8ICBfIFwgLyBfIFwvIF9fX3wgCiB8IHxfKSB8IHxffCB8IC8gXyBcIHwgfF8pIHwgfCB8IFxfX18gXCAKIHwgIF9fL3wgIF8gIHwvIF9fXyBcfCAgXyA8fCB8X3wgfF9fXykgfAogfF98ICAgfF98IHxfL18vICAgXF9cX3wgXF9cXF9fXy98X19fXy8gCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAK'


@click.group()
@click.option('--debug/--no-debug', is_flag=True, default=False, help='Debug mode')
@click.version_option()
def cli(debug):
    click.secho(base64.b64decode(B_LOGO).decode(), fg='green')
    click.echo('Debug mode is %s' % ('on' if debug else 'off'))
    logs.set_debug(debug)


@cli.command(help='Generate domain files')
@click.argument('deploy_file', default='deploy.json', type=click.Path(exists=True))
@click.option("--genesis", "-g", is_flag=True, help="need generate genesis")
@click.option("--key_passwd", default="", help="key passwd")
def generate(deploy_file,genesis,key_passwd):
    click.echo(click.format_filename(deploy_file))
    entrance.generate(deploy_file, genesis, key_passwd)

@cli.command(help="Generate genesis files")
@click.argument("deploy_file", default="deploy.json", type=click.Path(exists=True))
def generate_genesis(deploy_file):
    click.echo(click.format_filename(deploy_file))
    entrance.generate_genesis(deploy_file)


# Deploy command removed - deployment flow simplified to: generate -> bootstrap -> start
    
@cli.command(help='find fork between two domains')
@click.argument('domain1', nargs=1, type=click.Path(exists=True), required=True)
@click.argument('domain2', nargs=1, type=click.Path(exists=True), required=True)
@click.argument('start', nargs=1, type=str, default='written')
@click.option('--statefork', '-sf', is_flag=True, help='Check state fork')
def diff(domain1, domain2, start, statefork):
    entrance.diff(domain1, domain2, start, statefork)
    
@cli.command(help='query using jsonrpc')
@click.argument('domain_file', nargs=1, type=click.Path(exists=True), required=True)
@click.argument('type', nargs=1, type=str, required=True)
@click.argument('args', nargs=-1, type=str, required=False)
def query(domain_file, type, args):
    entrance.query(domain_file, type, args)
    
@cli.command(help='Clone data base from src_domain to dest_domains')
@click.argument('src_domain', nargs=1, type=click.Path(exists=True), required=True)
@click.argument('dest_domains', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--cold', help='clone src domain by cold db copy', is_flag=True, default=False)
@click.option('--backup', help='backup dest domain data before clone', is_flag=True, default=False)
def clone(src_domain, dest_domains, cold, backup):
    for domain_file in dest_domains:
        click.echo(click.format_filename(domain_file))
    entrance.clone(src_domain, dest_domains, cold, backup)

@cli.command(help='Add a non validator domain to the network of source domain')
@click.argument('src_domain', nargs=1, type=click.Path(exists=True), required=True)
@click.argument('dest_domains', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--cold', help='clone src domain by cold db copy', is_flag=True, default=False)
@click.option('--backup', help='backup dest domain database', is_flag=True, default=False)
def add_domain(src_domain, dest_domains, cold, backup):
    for domain_file in dest_domains:
        click.echo(click.format_filename(domain_file))
    entrance.bootstrap(dest_domains)
    entrance.clone(src_domain, dest_domains, cold, backup)
    entrance.start(dest_domains, None, '')
    
@cli.command(help='Change a non validator domain to validator domain')
@click.option('--endpoint', type=str, required=True)
@click.option('--key', type=str, default='fcfc69bd0056a2592e1f46cfba8264d8918fe98ecf5a2ef43aaa4ed1463725e1')
@click.argument('domains', nargs=-1, type=click.Path(exists=True), required=True)
def add_validator(endpoint, key, domains):
    for domain_file in domains:
        click.echo(click.format_filename(domain_file))
    entrance.add_validator(endpoint, key, domains)
    
@cli.command(help='Change a validator domain to non validator domain')
@click.option('--endpoint', type=str, required=True)
@click.option('--key', type=str, default='fcfc69bd0056a2592e1f46cfba8264d8918fe98ecf5a2ef43aaa4ed1463725e1')
@click.argument('domains', nargs=-1, type=click.Path(exists=True), required=True)
def exit_validator(endpoint, key, domains):
    for domain_file in domains:
        click.echo(click.format_filename(domain_file))
    entrance.exit_validator(endpoint, key, domains)


@cli.command(help='Clean with $domain_label.json')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--service', '-s', help='service [etcd|mygrid_service|portal|dog|txpool|controller|compute]]')
@click.option('--all', default=False, is_flag=True, help='clean up all data include conf')
def clean(domain_files, service, all):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.clean(domain_files, service, all)


@cli.command(help='Generate genesis state with $domain_label.json, old data and logs will be cleanup')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
def bootstrap(domain_files):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.bootstrap(domain_files)


@cli.command(help='Status with $domain_label.json')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--service', '-s', help='service [etcd|mygrid_service|portal|dog|txpool|controller|compute]]')
def status(domain_files, service):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.status(domain_files, service)


@cli.command(help='Start with $domain_label.json')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--service', '-s', help='service [etcd|mygrid_service|portal|dog|txpool|controller|compute]]')
@click.option('--extra-mygrid_service-args', '-a', help='extra storage args for storage start command', required=False)
def start(domain_files, service, extra_mygrid_service_args):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.start(domain_files, service, extra_mygrid_service_args)


@cli.command(help='Restart with $domain_label.json')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--service', '-s', help='service [etcd|mygrid_service|portal|dog|txpool|controller|compute]]')
@click.option('--extra-mygrid_service-args', '-a', help='extra storage args for storage start command', required=False)
def restart(domain_files, service, extra_mygrid_service_args):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.restart(domain_files, service, extra_mygrid_service_args)


@cli.command(help='Stop with $domain_label.json')
@click.argument('domain_files', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('--service', '-s', help='service [etcd|mygrid_service|portal|dog|txpool|controller|compute]]')
@click.option('--force', '-f', is_flag=True, default=False, help='Force stop')
def stop(domain_files, service, force):
    for domain_file in domain_files:
        click.echo(click.format_filename(domain_file))
    entrance.stop(domain_files, service, force)


@cli.command(help='Prepare integration testing')
@click.option('--job', envvar='ACI_JOB_NAME', default='')
@click.option('--branch', envvar='ACI_COMMIT_REF_NAME', default='master')
@click.option('--repo', envvar='ACI_REPOSITORY_URL', default='')
@click.option('--user', envvar='ACI_USER_LOGIN', default='')
@click.option('--workspace', envvar='WORKSPACE', default='')
@click.option('--pipeline-id', envvar='ACI_EXEC_ID', default='')
@click.option('--punch-chain', is_flag=True, default=False)
@click.option('--deploy-mode', envvar='DEPLOY_MODE', default='ultra')
def pre_systest(job: str, branch: str, repo: str, user: str, workspace: str, pipeline_id: str,
         punch_chain: bool, deploy_mode: str):
    print(os.environ)
    ctx = context.Context()
    ctx.job = job
    ctx.branch = branch
    ctx.repo = repo
    ctx.user = user
    ctx.workspace = workspace
    ctx.pipeline_id = pipeline_id
    if punch_chain:
        os.chdir(workspace)
        iplist = [ip.strip() for ip in open('iplist').read().split(" ") if len(ip) > 0]
    else:
        iplist = ['127.0.0.1']
    if len(iplist) == 0:
        logs.fatal('iplist is empty')
    ctx.iplist = iplist
    ctx.deploy_mode = deploy_mode
    systest.prepare_ssh(ctx)
    systest.prepare_pharos(ctx)
    systest.prepare_systest(ctx)
    sys.exit(0)


@cli.command(help='Run integration testing')
def run_systest():
    sys.exit(systest.run())


@cli.command(help='Post integration testing')
@click.option('--job', envvar='ACI_JOB_NAME', default='')
@click.option('--branch', envvar='ACI_COMMIT_REF_NAME', default='master')
@click.option('--repo', envvar='ACI_REPOSITORY_URL', default='')
@click.option('--user', envvar='ACI_USER_LOGIN', default='')
@click.option('--workspace', envvar='WORKSPACE', default='')
@click.option('--pipeline-id', envvar='ACI_EXEC_ID', default='')
@click.option('--punch-chain', is_flag=True, default=False)
@click.option('--deploy-mode', envvar='DEPLOY_MODE', default='ultra')
def post_systest(job: str, branch: str, repo: str, user: str, workspace: str, pipeline_id: str,
         punch_chain: bool, deploy_mode: str):
    print(os.environ)
    ctx = context.Context()
    ctx.job = job
    ctx.branch = branch
    ctx.repo = repo
    ctx.user = user
    ctx.workspace = workspace
    ctx.pipeline_id = pipeline_id
    if punch_chain:
        os.chdir(workspace)
        iplist = [ip.strip() for ip in open('iplist').read().split(" ") if len(ip) > 0]
    else:
        iplist = ['127.0.0.1']
    if len(iplist) == 0:
        logs.fatal('iplist is empty')
    ctx.iplist = iplist
    ctx.deploy_mode = deploy_mode
    systest.collect_logs(ctx)
    sys.exit(systest.handle_report(ctx))
    

@cli.command(help='Preapre bvt testing')
@click.option('--job', envvar='ACI_JOB_NAME', default='')
@click.option('--branch', envvar='ACI_COMMIT_REF_NAME', default='master')
@click.option('--repo', envvar='ACI_REPOSITORY_URL', default='')
@click.option('--user', envvar='ACI_USER_LOGIN', default='')
@click.option('--workspace', envvar='WORKSPACE', default='')
@click.option('--pipeline-id', envvar='ACI_EXEC_ID', default='')
@click.option('--punch-chain', is_flag=True, default=False)
@click.option('--deploy-mode', envvar='DEPLOY_MODE', default='ultra')
def pre_bvttest(job: str, branch: str, repo: str, user: str, workspace: str, pipeline_id: str,
         punch_chain: bool, deploy_mode: str):
    print(os.environ)
    ctx = context.Context()
    ctx.job = job
    ctx.branch = branch
    ctx.repo = repo
    ctx.user = user
    ctx.workspace = workspace
    ctx.pipeline_id = pipeline_id
    if punch_chain:
        os.chdir(workspace)
        iplist = [ip.strip() for ip in open('iplist').read().split(" ") if len(ip) > 0]
    else:
        iplist = ['127.0.0.1']
    if len(iplist) == 0:
        logs.fatal('iplist is empty')
    ctx.iplist = iplist
    ctx.deploy_mode = deploy_mode
    bvt.prepare_ssh(ctx)
    bvt.prepare_pharos(ctx)
    sys.exit(0)


@cli.command(help='Run bvt testing')
@click.argument('flow_file', default='flow.json', type=click.Path(exists=True))
def run_bvttest(flow_file: str):
    sys.exit(bvt.run(flow_file))


@cli.command(help='Post bvt testing')
@click.option('--job', envvar='ACI_JOB_NAME', default='')
@click.option('--branch', envvar='ACI_COMMIT_REF_NAME', default='master')
@click.option('--repo', envvar='ACI_REPOSITORY_URL', default='')
@click.option('--user', envvar='ACI_USER_LOGIN', default='')
@click.option('--workspace', envvar='WORKSPACE', default='')
@click.option('--pipeline-id', envvar='ACI_EXEC_ID', default='')
@click.option('--punch-chain', is_flag=True, default=False)
@click.option('--deploy-mode', envvar='DEPLOY_MODE', default='ultra')
def post_bvttest(job: str, branch: str, repo: str, user: str, workspace: str, pipeline_id: str,
         punch_chain: bool, deploy_mode: str):
    print(os.environ)
    ctx = context.Context()
    ctx.job = job
    ctx.branch = branch
    ctx.repo = repo
    ctx.user = user
    ctx.workspace = workspace
    ctx.pipeline_id = pipeline_id
    if punch_chain:
        os.chdir(workspace)
        iplist = [ip.strip() for ip in open('iplist').read().split(" ") if len(ip) > 0]
    else:
        iplist = ['127.0.0.1']
    if len(iplist) == 0:
        logs.fatal('iplist is empty')
    ctx.iplist = iplist
    ctx.deploy_mode = deploy_mode
    bvt.collect_logs(ctx)
    sys.exit(0)


@cli.command(help="Set public ip")
@click.argument("ip", envvar="PUBLIC_IP", default="127.0.0.1")
@click.argument("deploy_file", default="deploy.light.json")
def set_ip(ip: str, deploy_file: str):
    if ip == "127.0.0.1":
        logs.fatal("Please set public ip")
        return
    try:
        ipaddress.ip_address(ip)
    except ValueError as e:
        logs.fatal(f"Invalid ip: {e}")
        return
    with open(deploy_file, "r") as fh:
        deploy_data = json.load(fh)
        deploy = DeploySchema().load(deploy_data)
        for _, v in deploy.domains.items():
            for d in v.cluster:
                d.host = ip
        with open(deploy_file, "w") as fh:
            json.dump(DeploySchema().dump(deploy), fh, indent=2)
    logs.info(f"Set public ip to {ip}")

@cli.command(help="Update validator domain")
@click.option("--endpoint", type=str, required=True)
@click.argument(
    "key",
    type=str,
)
@click.argument("poolid", type=str,required=True)
@click.argument("new_owner", type=str,required=True)
@click.argument("domains", nargs=-1, type=click.Path(exists=True), required=True)
def update_validator(endpoint, key, poolid, domains,new_owner):
    entrance.update_validator(endpoint, key, domains, poolid, new_owner)


@cli.command(help="Upgrade pharos")
def upgrade():
    entrance.upgrade()
