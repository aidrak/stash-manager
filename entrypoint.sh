#!/bin/sh

CONFIG_DIR="/config"

# Create config directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Config directory not found. Creating $CONFIG_DIR..."
    mkdir -p "$CONFIG_DIR"
fi

# Ensure the config directory has the correct permissions
chown -R nobody:users "$CONFIG_DIR"

# Start the web application with Flask
echo "Starting web application with Flask..."
export PYTHONPATH=/home/nobody:$PYTHONPATH
export FLASK_APP=src.app:app
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=5001
cd /home/nobody
exec python -m flask run
