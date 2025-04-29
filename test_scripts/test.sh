#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <FOLDER_PATH>"
  exit 1
fi

DIR=$(dirname $(realpath $0))
FOLDER_PATH=$1
PYTHON_PATH=$(which python)
PORT_RECV=40000
PORT_SEND=50000
WINDOW_SIZE=128
ERROR_TYPES=0123

# Kill previous ports first
PREV_PIDS=$(sudo lsof -ti:$PORT_RECV,$PORT_SEND)
if [ -n "$PREV_PIDS" ]; then
  sudo kill -9 $PREV_PIDS
fi

echo -n "Step 1: Start the receiver"
$PYTHON_PATH $FOLDER_PATH/receiver.py localhost $PORT_RECV $WINDOW_SIZE > $FOLDER_PATH/output.txt &
RECEIVER_PID=$!
echo -e " (process $RECEIVER_PID)"
sleep 1

echo -n "Step 2: Start the proxy"
$PYTHON_PATH $DIR/proxy.py localhost $PORT_SEND localhost $PORT_RECV $ERROR_TYPES > /dev/null &
PROXY_PID=$!
echo -e " (process $PROXY_PID)"
sleep 1

echo -n "Step 3: Start the sender"
$PYTHON_PATH $FOLDER_PATH/sender.py localhost $PORT_SEND $WINDOW_SIZE < $DIR/test_message.txt > /dev/null &
SENDER_PID=$!
echo -e " (process $SENDER_PID)"

echo "Waiting 10 seconds for all to finish"
sleep 10
sudo kill -INT $RECEIVER_PID $PROXY_PID $SENDER_ID

echo "Step 4: Compare the results"
$DIR/compare.sh $FOLDER_PATH/output.txt $DIR/test_message.txt
