#!/bin/bash

set -e

/usr/sbin/sshd

external_ip=$(curl -s ifconfig.me || ip route get 1 | awk '{print $7; exit}')

if [ ! -d /data/pharos-node ]; then
    cd /app/scripts

    # Set public IP in pharos.conf
    /root/.local/bin/pipenv run pharos --no-debug set-ip "$external_ip" /app/conf/pharos.conf
    
    # Copy necessary files to /data
    /bin/cp -rf /app/scripts/resources /data
    /bin/cp -f ../genesis.conf /data/genesis.conf
    /bin/cp -f ../conf/pharos.conf /data/pharos.conf

    # Run bootstrap without domain.json
    /root/.local/bin/pipenv run pharos --no-debug bootstrap
    
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
    /bin/cp -rf /data/resources /app/scripts
    /bin/cp -f /data/pharos-node/domain/client/conf/genesis.conf /app/conf/

    /bin/cp -f /app/bin/pharos_cli /data/pharos-node/domain/client/bin/

    cd /data/pharos-node/domain/light/bin/
    exec env LD_PRELOAD=./libevmone.so ./pharos_light -c ../conf/pharos.conf
fi
