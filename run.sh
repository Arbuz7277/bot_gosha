#!/bin/bash
# Starts the bot inside the local virtualenv.
cd "$(dirname "$0")" || exit 1
source venv/bin/activate
exec python3 main.py
