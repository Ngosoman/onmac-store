#!/bin/bash
set -euo pipefail
cd /home/site/wwwroot
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn --bind=0.0.0.0 --timeout 600 config.wsgi
