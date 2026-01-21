#!/bin/bash

set -e

# Configuration
PHAROS_CONF="${PHAROS_CONF:-/data/pharos.conf}"
GENESIS_CONF="${GENESIS_CONF:-/data/genesis.conf}"
KEYS_DIR="${KEYS_DIR:-/data/keys}"

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
    /app/ops generate-keys -o "$KEYS_DIR"
    echo "Keys generated successfully"
else
    echo "Found existing keys in $KEYS_DIR"
fi

# Extract data path from pharos.conf
CONFIG_DATA_PATH=$(grep -oP '"meta_data"\s*:\s*"\K[^"]+' "$PHAROS_CONF" 2>/dev/null || echo "")

if [ -z "$CONFIG_DATA_PATH" ]; then
    echo "Error: Could not extract meta_data from pharos.conf"
    exit 1
fi

# Convert relative path to absolute based on working directory
# If path starts with ../, resolve it relative to /app/bin
if [[ "$CONFIG_DATA_PATH" == ../* ]]; then
    RESOLVED_DATA_PATH="/app/$(echo "$CONFIG_DATA_PATH" | sed 's|^\.\./||')"
elif [[ "$CONFIG_DATA_PATH" == ./* ]]; then
    RESOLVED_DATA_PATH="/app/bin/$(echo "$CONFIG_DATA_PATH" | sed 's|^\./||')"
else
    RESOLVED_DATA_PATH="$CONFIG_DATA_PATH"
fi

# Check if meta_store exists to determine if already bootstrapped
if [ -d "${RESOLVED_DATA_PATH}/meta_store" ]; then
    echo "Found existing data at ${RESOLVED_DATA_PATH}/meta_store"
    BOOTSTRAPPED=true
else
    echo "No existing data found at ${RESOLVED_DATA_PATH}/meta_store"
    BOOTSTRAPPED=false
fi

cd /app/bin

if [ "$BOOTSTRAPPED" = false ]; then
    # Check if genesis.conf exists (required for bootstrap)
    if [ ! -f "$GENESIS_CONF" ]; then
        echo "Error: genesis.conf not found at $GENESIS_CONF"
        echo "Please mount genesis.conf to $GENESIS_CONF for initial bootstrap"
        exit 1
    fi
    
    echo "Bootstrapping node..."
    echo "Running: pharos_cli genesis -c $PHAROS_CONF -g $GENESIS_CONF"
    
    # Run bootstrap as main process
    exec env LD_PRELOAD=./libevmone.so \
        CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
        PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
        ./pharos_cli genesis -c "$PHAROS_CONF" -g "$GENESIS_CONF"
else
    echo "Starting pharos node..."
    echo "Running: pharos_light -c $PHAROS_CONF"
    
    # Start pharos_light as main process (PID 1)
    exec env LD_PRELOAD=./libevmone.so \
        CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
        PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
        ./pharos_light -c "$PHAROS_CONF"
fi
