#!/usr/bin/env bash

set -ex

COMMAND="${*:-start}"
GLANCE_CONF="${GLANCE_CONF:-/etc/glance/glance-api.conf}"

function setup_database() {
  echo "Setting up database..."

  if [ -z "${SKIP_GLANCE_DB_SYNC}" ]; then
    echo "Syncing database schema..."
    glance-manage --config-file "${GLANCE_CONF}" db_sync || {
      echo "ERROR: Database sync failed"
      return 1
    }
  else
    echo "Skipping database sync as SKIP_GLANCE_DB_SYNC is set"
  fi

  return 0
}

function start() {

  if [ -d "/var/lib/glance" ]; then
    chown -R "$(id -u glance):$(id -g glance)" /var/lib/glance
    chmod -R 765 /var/lib/glance
  fi

  # Initialize database
  setup_database || {
    echo "ERROR: Database setup failed"
    exit 1
  }

  exec uwsgi --uid glance --gid glance --offload-threads 4
}

function stop() {
  echo "Stopping Glance API..."
  kill -TERM 1
}

# Main command handler
case "$COMMAND" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  *)
    echo "Unknown command: $COMMAND"
    echo "Usage: $0 [start|stop]"
    exit 1
    ;;
esac
