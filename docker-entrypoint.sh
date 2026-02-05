#!/bin/bash

set -e

# Configuration
PHAROS_CONF="${PHAROS_CONF:-/data/pharos.conf}"
GENESIS_CONF="${GENESIS_CONF:-/data/genesis.conf}"
KEYS_DIR="${KEYS_DIR:-/data/keys}"
DATA_DIR="${DATA_DIR:-/data/data}"

echo "=== Pharos Node Startup ==="

# Copy binaries from /app to /data (always refresh to ensure latest version)
echo "Copying binaries from /app/bin to /data/bin..."

# Backup VERSION file if exists
if [ -f "/data/bin/VERSION" ]; then
    cp /data/bin/VERSION /tmp/VERSION.bak
fi

rm -rf /data/bin
cp -r /app/bin /data/bin
chmod +x /data/bin/*

# Restore VERSION file if was backed up
if [ -f "/tmp/VERSION.bak" ]; then
    cp /tmp/VERSION.bak /data/bin/VERSION
    rm -f /tmp/VERSION.bak
    echo "Restored user-provided VERSION file"
fi

# Copy ops tool
echo "Copying ops tool..."
cp /app/ops /data/ops
chmod +x /data/ops

echo "Binaries copied successfully"

# Check if pharos.conf exists
if [ ! -f "$PHAROS_CONF" ]; then
    echo "Error: pharos.conf not found at $PHAROS_CONF"
    echo "Please mount pharos.conf to $PHAROS_CONF"
    exit 1
fi

# Check password environment variable
if [ -z "$CONSENSUS_KEY_PWD" ]; then
    echo "Error: CONSENSUS_KEY_PWD environment variable not set"
    echo "Please set it in docker-compose.yml or docker run command"
    exit 1
fi

# Set PORTAL_SSL_PWD to same value if not set
export PORTAL_SSL_PWD="${PORTAL_SSL_PWD:-$CONSENSUS_KEY_PWD}"

# Check if keys exist, if not generate them
if [ ! -f "$KEYS_DIR/domain.key" ] || [ ! -f "$KEYS_DIR/stabilizing.key" ]; then
    echo "Keys not found in $KEYS_DIR, generating new keys..."
    mkdir -p "$KEYS_DIR"
    /data/ops generate-keys -o "$KEYS_DIR"
    echo "Keys generated successfully"
else
    echo "Found existing keys in $KEYS_DIR"
fi

# Check if meta_store exists to determine if already bootstrapped
# Config uses ../data which resolves to /data/data when working dir is /data/bin
if [ -d "${DATA_DIR}/meta_store" ]; then
    echo "Found existing data at ${DATA_DIR}/meta_store"
    BOOTSTRAPPED=true
else
    echo "No existing data found at ${DATA_DIR}/meta_store"
    BOOTSTRAPPED=false
fi

# Change to bin directory so relative paths in config work correctly
cd /data/bin

if [ "$BOOTSTRAPPED" = false ]; then
    # Check if genesis.conf exists (required for bootstrap)
    if [ ! -f "$GENESIS_CONF" ]; then
        echo "Error: genesis.conf not found at $GENESIS_CONF"
        echo "Please mount genesis.conf to $GENESIS_CONF for initial bootstrap"
        exit 1
    fi
    
    echo "Bootstrapping node..."
    echo "Running: pharos_cli genesis -c $PHAROS_CONF -g $GENESIS_CONF"
    
    # Run bootstrap (not as exec, so we can continue after)
    env LD_PRELOAD=./libevmone.so \
        CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
        PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
        ./pharos_cli genesis -c "$PHAROS_CONF" -g "$GENESIS_CONF"
    
    echo "Bootstrap completed successfully"
fi

echo "Starting pharos node..."
echo "Running: pharos_light -c $PHAROS_CONF"

# Start pharos_light as main process (PID 1)
exec env LD_PRELOAD=./libevmone.so \
    CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
    PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
    ./pharos_light -c "$PHAROS_CONF"
