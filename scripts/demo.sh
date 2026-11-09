#!/bin/sh
# Local college demo on an ISOLATED scratch database (biopay_demo). Never touches the real `biopay`
# database or your .env. Local trust auth for the current OS user; every secret is generated.
# Usage: scripts/demo.sh start | stop | reset (drops ONLY biopay_demo) | creds
cd "$(dirname "$0")/.." || exit 1
PIDS=.demo-pids          # git-ignored: only OUR servers are ever stopped, never other dev servers
CREDS=.demo-credentials   # git-ignored, mode 600: holds the generated demo password
DB=biopay_demo

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1 ($2)"; exit 1; }; }
check() {
  need psql "install PostgreSQL: brew install postgresql@16"; need node "install Node 20+"; need python3 ""
  pg_isready -q -h 127.0.0.1 || { echo "PostgreSQL is not running on 127.0.0.1:5432 (brew services start postgresql@16)"; exit 1; }
  [ -x .venv/bin/python ] || { echo "Missing .venv: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
  [ -d web/node_modules ] || { echo "Missing web/node_modules: (cd web && npm install)"; exit 1; }
}
env_setup() {
  [ -f "$CREDS" ] || { python3 -c 'import secrets;print(secrets.token_urlsafe(18))' > "$CREDS"; chmod 600 "$CREDS"; }
  export BIOPAY_DEMO_PASSWORD="$(cat "$CREDS")"
  export DJANGO_SECRET_KEY="demo-only-$(python3 -c 'import secrets;print(secrets.token_urlsafe(40))')"
  export DJANGO_DEBUG=true BIOPAY_ENABLE_DEMO_API=true PGUSER="$(whoami)" PGDATABASE=$DB PGHOST=127.0.0.1
  export BIOPAY_DEMO_TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(40))')"
}
case "$1" in
  start)
    check; env_setup
    psql -h 127.0.0.1 -d postgres -tc "select 1 from pg_database where datname='$DB'" | grep -q 1 || createdb -h 127.0.0.1 $DB
    .venv/bin/python manage.py migrate -v0 && .venv/bin/python manage.py seed_demo_users >/dev/null || exit 1
    "$0" stop >/dev/null
    for port in 8000 5173; do
      lsof -ti tcp:$port -sTCP:LISTEN >/dev/null 2>&1 && { echo "Port $port is used by another program; stop it first."; exit 1; }
    done
    nohup .venv/bin/python manage.py runserver --noreload 127.0.0.1:8000 >/tmp/biopay-django.log 2>&1 </dev/null &
    echo $! > "$PIDS"
    cd web || exit 1
    nohup node_modules/.bin/vite --port 5173 --host 127.0.0.1 >/tmp/biopay-vite.log 2>&1 </dev/null &
    echo $! >> "../$PIDS"
    cd ..
    sleep 4
    curl -fsS -m 5 http://127.0.0.1:5173/api/auth/me/ >/dev/null || { echo "Servers did not come up; see /tmp/biopay-*.log"; exit 1; }
    echo "Demo ready: http://127.0.0.1:5173/"
    echo "Logins: demo-customer, demo-merchant, demo-admin   password: $(cat $CREDS)";;
  stop) [ -f "$PIDS" ] && { xargs kill < "$PIDS" 2>/dev/null; rm -f "$PIDS"; }; echo stopped;;
  reset) "$0" stop; dropdb -h 127.0.0.1 --if-exists $DB && rm -f "$CREDS" && echo "biopay_demo dropped";;
  creds) cat "$CREDS";;
  *) echo "usage: $0 start|stop|reset|creds";;
esac
