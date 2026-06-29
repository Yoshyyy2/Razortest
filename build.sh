#!/bin/bash
set -e
pip install --upgrade pip
pip install greenlet==3.0.1 --only-binary=:all:
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps chromium
