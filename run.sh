#!/bin/bash

cd dp
python3 all_money.py &
echo "'dp/all_money.py' has been activated."
sleep 0.5
cd ..
python3 bot_control.py &
echo "'bot_control.py' has been activated."
sleep 0.5

./start.sh
kill %1
kill %2
echo "Bye!"
