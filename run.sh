#!/bin/bash

source venv/bin/activate

cd dp && python3 all_money.py &
cd .. && python3 bot_control.py &
./start.sh
