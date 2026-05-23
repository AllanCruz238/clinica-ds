#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input

python manage.py migrate core zero --fake || true
python manage.py migrate

python seed_admin.py