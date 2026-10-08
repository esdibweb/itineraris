#!/bin/sh
# Apply database migrations, then start the command (gunicorn by default)
set -e

python manage.py migrate --noinput

exec "$@"
