#!/bin/sh

# This script runs the main Python application in a loop.
# It's a simple way to ensure the script restarts if it exits.

while true
do
  python /usr/src/app/src/main.py
  echo "Application exited. Restarting in 10 seconds..."
  sleep 10
done
