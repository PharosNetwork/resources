#!/bin/bash

set -e

# Configuration
PYTHON_VERSION="3.6.15"
VENV_NAME="pharos_testnet"
BASHRC="$HOME/.bashrc"
PYENV_ROOT="$HOME/.pyenv"
SCRIPT_DIR="."
PREPARE_SCRIPT="$SCRIPT_DIR/ops_prepare.sh"
SSHD_CONFIG="/etc/ssh/sshd_config"

export PIPENV_PIPFILE=$(pwd)/Pipfile

# 1. Install system dependencies (always)
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev curl llvm libncurses5-dev libncursesw5-dev \
xz-utils tk-dev libffi-dev liblzma-dev

# 2. Install pyenv if not already installed
if [ ! -d "$PYENV_ROOT" ]; then
  echo "Installing pyenv..."
  curl https://pyenv.run | bash
fi

# Append pyenv initialization to .bashrc if missing
if ! grep -q 'export PYENV_ROOT' "$BASHRC"; then
  echo "Adding pyenv initialization to .bashrc..."
  {
    echo 'export PYENV_ROOT="$HOME/.pyenv"'
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"'
    echo 'eval "$(pyenv init -)"'
    echo 'alias pharos="~/.local/bin/pipenv run pharos"'
  } >> "$BASHRC"
fi

# Initialize pyenv for the current shell session
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# 3. Install the required Python version if not already installed
if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
  echo "Installing Python $PYTHON_VERSION..."
  pyenv install "$PYTHON_VERSION"
fi

# 4. Always recreate the virtual environment
echo "Setting up virtual environment $VENV_NAME..."
pyenv virtualenv -f "$PYTHON_VERSION" "$VENV_NAME"

# 5. Set the local Python version for the current directory
cd "$SCRIPT_DIR"
pyenv local "$VENV_NAME"

# 6. Ensure ~/.local/bin is in PATH
if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$BASHRC"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$BASHRC"
fi

# Apply updated PATH immediately
source "$BASHRC"

# Ensure ~/.local/bin exists BEFORE creating any symlinks inside it
mkdir -p "$HOME/.local/bin"

# Create symlink for ~/.local/bin/python pointing to virtualenv Python
TARGET_PYTHON_PATH="$PYENV_ROOT/versions/$VENV_NAME/bin/python"
LOCAL_BIN_PYTHON="$HOME/.local/bin/python"

if [ ! -L "$LOCAL_BIN_PYTHON" ] || [ "$(readlink -f "$LOCAL_BIN_PYTHON")" != "$(readlink -f "$TARGET_PYTHON_PATH")" ]; then
    echo "Creating symlink: $LOCAL_BIN_PYTHON → $TARGET_PYTHON_PATH"
    rm -f "$LOCAL_BIN_PYTHON" # Remove existing file or broken symlink
    ln -s "$TARGET_PYTHON_PATH" "$LOCAL_BIN_PYTHON"
fi

# Create symlink for ~/.local/bin/pipenv pointing to virtualenv pipenv
TARGET_PIPENV_PATH="$PYENV_ROOT/versions/$VENV_NAME/bin/pipenv"
LOCAL_BIN_PIPENV="$HOME/.local/bin/pipenv"

if [ ! -L "$LOCAL_BIN_PIPENV" ] || [ "$(readlink -f "$LOCAL_BIN_PIPENV")" != "$(readlink -f "$TARGET_PIPENV_PATH")" ]; then
    echo "Creating symlink: $LOCAL_BIN_PIPENV → $TARGET_PIPENV_PATH"
    rm -f "$LOCAL_BIN_PIPENV" # Remove existing file or broken symlink
    ln -s "$TARGET_PIPENV_PATH" "$LOCAL_BIN_PIPENV"
fi

# Activate the virtual environment and install pipenv
echo "Activating virtual environment '$VENV_NAME' and installing pipenv..."
source "$PYENV_ROOT/versions/$VENV_NAME/bin/activate"

if ! pip show pipenv &>/dev/null; then
    echo "INFO: Installing pipenv in $VENV_NAME"
    pip install pipenv==11.10.4 -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
else
    echo "INFO: pipenv is already installed in $VENV_NAME"
fi

# Deactivate virtual environment
deactivate

# 7. Run the preparation script if available
if [ -f "$PREPARE_SCRIPT" ]; then
  echo "Running ops_prepare.sh..."
  bash "$PREPARE_SCRIPT"
else
  echo "Prepare script not found: $PREPARE_SCRIPT"
fi

# 8. Ensure sshd_config includes required RSA algorithms
if ! grep -q '^PubkeyAcceptedAlgorithms +ssh-rsa' "$SSHD_CONFIG"; then
  echo "Adding PubkeyAcceptedAlgorithms to sshd_config..."
  echo 'PubkeyAcceptedAlgorithms +ssh-rsa' | sudo tee -a "$SSHD_CONFIG"
fi

if ! grep -q '^HostKeyAlgorithms +ssh-rsa' "$SSHD_CONFIG"; then
  echo "Adding HostKeyAlgorithms to sshd_config..."
  echo 'HostKeyAlgorithms +ssh-rsa' | sudo tee -a "$SSHD_CONFIG"
fi

echo "Restarting sshd..."
sudo systemctl restart ssh

echo "All steps completed successfully."
