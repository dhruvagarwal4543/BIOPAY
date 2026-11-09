#!/bin/sh
# Local demo on an ISOLATED scratch database (biopay_demo). Never touches the real `biopay` DB or .env.
# Usage: scripts/demo.sh start|stop. Local trust auth for the current OS user; throwaway secrets.
cd "$(dirname "$0")/.." || exit 1
export DJANGO_SECRET_KEY="demo-only-$(python3 -c 'import secrets;print(secrets.token_urlsafe(40))')"
export DJANGO_DEBUG=true BIOPAY_ENABLE_DEMO_API=true PGUSER="$(whoami)" PGDATABASE=biopay_demo PGHOST=127.0.0.1
export BIOPAY_DEMO_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(40))')"
export BIOPAY_DEMO_PASSWORD="${BIOPAY_DEMO_PASSWORD:-BioPay-Demo-2026}"
case "$1" in
  start)
    psql -d postgres -tc "select 1 from pg_database where datname='biopay_demo'" | grep -q 1 || createdb biopay_demo
    .venv/bin/python manage.py migrate -v0 && .venv/bin/python manage.py seed_demo_users
    nohup .venv/bin/python manage.py runserver 127.0.0.1:8000 > /tmp/biopay-django.log 2>&1 &
    (cd web && nohup npx vite --port 5173 --host 127.0.0.1 > /tmp/biopay-vite.log 2>&1 &)
    echo "Open http://127.0.0.1:5173/  (logins: demo-customer / demo-merchant / demo-admin, password: $BIOPAY_DEMO_PASSWORD)";;
  stop) pkill -f "manage.py runserver"; pkill -f "vite --port 5173";;
esac
