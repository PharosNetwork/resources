#!/usr/bin/env bash

BASEDIR=$(dirname $0)
cd $BASEDIR

echo "INFO: prepare pharos ops"

if [ ! -d "pharos-ops" ];then
    echo "ERROR: pharos-ops repo not found. You should `sh build.sh pharos_ops.repo` at workspace first."
    exit 1
    # echo "INFO: cloning pharos-ops.git"
    # git clone http://git-ci-token:a3e8e916bee846078a5fef32ad7249d3@git@github.com/pharoschain/pharos-ops.git
fi

# pharos-ops 需要配置本机免密登录
ssh_exist=$(ps -ef|grep /usr/sbin/sshd|grep -v "grep" | wc -l)
if [ 0 == $ssh_exist ]; then
    /usr/sbin/sshd -D &
fi
if [ ! -f ~/.ssh/id_rsa ]; then
    echo ssh-keygen ~/.ssh/id_rsa
    ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa -q
    cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
    chmod 600 ~/.ssh/authorized_keys
    ssh-copy-id -i ~/.ssh/id_rsa.pub -o StrictHostKeyChecking=no 127.0.0.1
fi

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8
pip3 show pipenv
if [ $? -ne 0 ];then
    echo "INFO: installing pipenv"
    pip3 install --user pipenv==11.10.4
fi

if [ ! -f "Pipfile" ];then
    echo "INFO: creating pipenv --python 3.6"
    unset PIPENV_PIPFILE
    ~/.local/bin/pipenv --python 3.6
fi

~/.local/bin/pipenv run pip show pharos-ops
if [ $? -ne 0 ];then
    echo "INFO: installing pharos-ops"
    ~/.local/bin/pipenv run pip install -e pharos-ops
fi
~/.local/bin/pipenv run pharos --version
