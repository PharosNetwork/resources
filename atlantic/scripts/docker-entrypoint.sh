#!/bin/bash

set -e

# Configuration
PHAROS_CONF="${PHAROS_CONF:-/data/pharos.conf}"
DATA_DIR="${DATA_DIR:-/data}"

# Extract data path from pharos.conf if it exists
if [ -f "$PHAROS_CONF" ]; then
    # Try to extract data_path from pharos.conf
    # This assumes the config has: "data_path": "../data" or similar
    CONFIG_DATA_PATH=$(grep -oP '"data_path"\s*:\s*"\K[^"]+' "$PHAROS_CONF" 2>/dev/null || echo "")
    
    if [ -n "$CONFIG_DATA_PATH" ]; then
        # Convert relative path to absolute based on working directory
        # If path starts with ../, resolve it relative to /app/bin
        if [[ "$CONFIG_DATA_PATH" == ../* ]]; then
            RESOLVED_DATA_PATH="/app/$(echo "$CONFIG_DATA_PATH" | sed 's|^\.\./||')"
        elif [[ "$CONFIG_DATA_PATH" == ./* ]]; then
            RESOLVED_DATA_PATH="/app/bin/$(echo "$CONFIG_DATA_PATH" | sed 's|^\./||')"
        else
            RESOLVED_DATA_PATH="$CONFIG_DATA_PATH"
        fi
        
        # Check if meta_store exists in the resolved path
        if [ -d "${RESOLVED_DATA_PATH}/meta_store" ]; then
            echo "Found existing data at ${RESOLVED_DATA_PATH}/meta_store"
            BOOTSTRAPPED=true
        else
            echo "No existing data found at ${RESOLVED_DATA_PATH}/meta_store"
            BOOTSTRAPPED=false
        fi
    else
        echo "Warning: Could not extract data_path from pharos.conf"
        BOOTSTRAPPED=false
    fi
else
    echo "Error: pharos.conf not found at $PHAROS_CONF"
    echo "Please mount pharos.conf to $PHAROS_CONF"
    exit 1
fi

# Check if genesis.conf exists (required for bootstrap)
GENESIS_CONF="${GENESIS_CONF:-/data/genesis.conf}"
if [ "$BOOTSTRAPPED" = false ] && [ ! -f "$GENESIS_CONF" ]; then
    echo "Error: genesis.conf not found at $GENESIS_CONF"
    echo "Please mount genesis.conf to $GENESIS_CONF for initial bootstrap"
    exit 1
fi

# Check if keys exist
KEYS_DIR="${KEYS_DIR:-/data/keys}"
if [ ! -f "$KEYS_DIR/domain.key" ] || [ ! -f "$KEYS_DIR/stabilizing.key" ]; then
    echo "Error: Keys not found in $KEYS_DIR"
    echo "Please generate keys first using: docker run --rm -v /data:/data <image> /app/ops generate-keys -o /data/keys"
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

cd /app/bin

if [ "$BOOTSTRAPPED" = false ]; then
    echo "Bootstrapping node..."
    echo "Running: pharos_cli genesis -c $PHAROS_CONF -g $GENESIS_CONF"
    
    # Run bootstrap
    exec env LD_PRELOAD=./libevmone.so \
        CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
        PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
        ./pharos_cli genesis -c "$PHAROS_CONF" -g "$GENESIS_CONF"
    
    # After bootstrap completes, the container will restart and go to the else branch
else
    echo "Starting pharos node..."
    echo "Running: pharos_light -c $PHAROS_CONF"
    
    # Start pharos_light as the main process (PID 1)
    exec env LD_PRELOAD=./libevmone.so \
        CONSENSUS_KEY_PWD="$CONSENSUS_KEY_PWD" \
        PORTAL_SSL_PWD="$PORTAL_SSL_PWD" \
        ./pharos_light -c "$PHAROS_CONF"
fi
