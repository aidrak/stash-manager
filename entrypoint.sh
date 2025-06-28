#!/bin/sh

CONFIG_FILE="/config/config.yaml"
SAMPLE_FILE="/config/config.yaml.sample"

# Check if config.yaml exists, if not, copy from sample
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file not found. Copying from sample..."
    cp "$SAMPLE_FILE" "$CONFIG_FILE"
fi

# Start the cron daemon in the background
cron

# Run the loop-runner.sh script
/usr/src/app/loop-runner.sh
