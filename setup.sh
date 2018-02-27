#!/bin/sh

if ! which python3; then
    echo "Install Python 3."
    return 1
fi

python3 -m venv venv
. venv/bin/activate

pip install flask flask-misaka flask-wtf ruamel.yaml


