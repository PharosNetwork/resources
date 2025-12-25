#!/bin/bash

set -e

/usr/sbin/sshd

external_ip=$(curl -s ifconfig.me || ip route get 1 | awk '{print $7; exit}')

if [ ! -d /data/pharos-node ]; then
    cd /app/scripts

    sed -i "s/\"host\": \"127.0.0.1\"/\"host\": \"$external_ip\"/" /app/scripts/deploy.light.json
    /root/.local/bin/pipenv run pharos --no-debug generate /app/scripts/deploy.light.json
    /bin/cp -rf /app/scripts/resources /data
    sed -i 's|\"../conf/genesis.pharos-node.conf\"|\"/data/genesis.conf\"|g' /app/scripts/domain.json
    /bin/cp -f domain.json /data/
    /bin/cp -f deploy.light.json /data/
    /bin/cp -f ../genesis.conf /data/genesis.conf

    /root/.local/bin/pipenv run pharos --no-debug deploy /app/scripts/domain.json
    /root/.local/bin/pipenv run pharos --no-debug bootstrap /app/scripts/domain.json
    cd /data/pharos-node/domain/light/bin/
    exec env LD_PRELOAD=./libevmone.so ./pharos_light -c ../conf/pharos.conf
else
    rm -f /data/pharos-node/domain/light/bin/libevmone.so
    rm -f /data/pharos-node/domain/light/bin/pharos_light
    rm -f /data/pharos-node/domain/light/bin/VERSION
    rm -f /data/pharos-node/domain/client/bin/pharos_cli
    rm -f /data/pharos-node/domain/client/bin/libevmone.so

    ln -s /app/bin/libevmone.so /data/pharos-node/domain/client/bin/libevmone.so
    ln -s /app/bin/libevmone.so /data/pharos-node/domain/light/bin/libevmone.so
    ln -s /app/bin/pharos_light /data/pharos-node/domain/light/bin/pharos_light
    ln -s /app/bin/VERSION /data/pharos-node/domain/light/bin/VERSION

    cd /app/scripts
    /bin/cp -f /data/domain.json .
    /bin/cp -rf /data/resources /app/scripts
    /bin/cp -f /data/pharos-node/domain/client/conf/genesis.conf /app/conf/

    /bin/cp -f /app/bin/pharos_cli /data/pharos-node/domain/client/bin/
    /bin/cp -f /data/deploy.light.json .

    ~/.local/bin/pipenv run pharos update-conf domain.json
    cd /data/pharos-node/domain/light/bin/
    exec env LD_PRELOAD=./libevmone.so ./pharos_light -c ../conf/pharos.conf
fi
