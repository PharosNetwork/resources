#!/usr/bin/env python3
# coding=utf-8
from aldaba_ops.toolkit import utils

import sys
import os
import subprocess
import glob
import time
import shutil


MYCHAIN_OSS_PREFIX = "https://antsys-mychain.cn-hangzhou-alipay-b.oss-cdn.aliyun-inc.com"


def mycp(s, d):
    print('copy', s, d)
    shutil.copy(s, d)


def myrm(path):
    print('rm', path)
    fullpath = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path) or os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(fullpath):
        shutil.rmtree(fullpath)
    else:
        for f in glob.glob(fullpath):
            myrm(f)


def tar_dir(tarname, dirs, compress="w"):
    print('tar', tarname, dirs)
    import tarfile
    tar = tarfile.open(tarname, compress)
    for d in dirs:
        tar.add(d)
    tar.close()


def extract_tar(fn, out="."):
    print('untar', fn, out)
    import tarfile
    tar = tarfile.open(fn, "r")
    tar.extractall(out)
    tar.close()


def download(url, target_dir=None):
    print('download', url, target_dir)
    filename = os.path.basename(url)
    if target_dir:
        filename = os.path.join(target_dir, filename)
    if os.path.exists(filename):
        myrm(filename)
    cnt = 3
    err_msg = "download " + url
    print(err_msg)
    while cnt > 0:
        try:
            utils.must_exec_run('wget -O {} {}'.format(filename, url))
            break
        except Exception as e:
            # print(err_msg + " error: ", e)
            cnt -= 1
            time.sleep(5)
    if cnt == 0:
        raise Exception(err_msg)
    return True


def upload_log(l_fp, r_fp):
    print('upload_log', l_fp, r_fp)
    # upload_ftp
    # exec_no_print("""
    #     curl --ftp-create-dirs \
    #     -T "{0}" \
    #     -u ftpuser:mychain123 \
    #     "{1}/{2}"
    # """.format(l_fp, 'ftp://mychainftp.inc.alipay.net/test/log', r_fp))
    # upload_oss
    print("download oss tool")
    utils.must_exec_run("curl -O " + MYCHAIN_OSS_PREFIX + "/mychain-0.10/ci_config/ossutil64")
    utils.must_exec_run("curl -O " + MYCHAIN_OSS_PREFIX + "/mychain-0.10/ci_config/ossconfig")
    oss_target = "oss://antsys-mychain/platform-ci-test/aldaba/{}".format(r_fp)
    print("upload local file:{} to oss:{}".format(l_fp, oss_target))
    utils.must_exec_run("chmod +x ossutil64")
    cmd = "./ossutil64 cp {} {} --config-file=ossconfig -f".format(l_fp, oss_target)
    print(cmd)
    utils.must_exec_run(cmd)


def exec_no_print(cmd, log_fd=sys.stdout, **kwargs):
    ret = True
    output = ""
    try:
        if os.name != "nt" and type(cmd) is list:
            cmd = " ".join(cmd)
        output = subprocess.check_output(cmd, stderr=log_fd, shell=True, **kwargs)
        output = output.decode("utf-8").strip()
    except subprocess.CalledProcessError as e:
        # print_trace(e)
        print("$" * 20, e)
        log_fd.write(str(e))
        log_fd.flush()
        ret = False
    return ret, output