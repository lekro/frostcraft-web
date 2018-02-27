#!/bin/sh

. venv/bin/activate

export FLASK_APP=frostcraft.py
flask run
