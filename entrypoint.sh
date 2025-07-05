#!/bin/sh

CONFIG_DIR="/config"

# Create config directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Config directory not found. Creating $CONFIG_DIR..."
    mkdir -p "$CONFIG_DIR"
fi

# Ensure the config directory has the correct permissions
chown nobody:users "$CONFIG_DIR"

# Start the web application, replacing the shell process with the Python process
echo "Starting web application..."
cd /home/nobody
export PYTHONPATH=/home/nobody:$PYTHONPATH
exec gosu nobody python src/app.py
