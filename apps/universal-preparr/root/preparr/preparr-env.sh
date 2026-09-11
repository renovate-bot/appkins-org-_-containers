#!/usr/bin/env bash
# Shared helpers for the universal-preparr mod, sourced by the init oneshot and
# the sidecar longrun. PrepArr reads everything from the environment, so all this
# does is fill in the values a mod can work out for itself.

PREPARR_HOME="/preparr"
PREPARR_BIN="${PREPARR_HOME}/bun"
PREPARR_ENTRYPOINT="${PREPARR_HOME}/dist/index.js"
PREPARR_RUNTIME_DIR="/run/preparr"
PREPARR_SKIP_FILE="${PREPARR_RUNTIME_DIR}/skip"

preparr_log() {
  echo "[preparr] $*"
}

preparr_runtime_dir() {
  mkdir -p "${PREPARR_RUNTIME_DIR}"
  chown abc:abc "${PREPARR_RUNTIME_DIR}"
}

# Never exit a longrun immediately - s6 would just respawn it in a tight loop.
preparr_park() {
  while true; do
    sleep 3600
  done
}

# Default web UI port per app, used when config.xml has no <Port> yet.
preparr_default_port() {
  case "$1" in
    radarr) echo 7878 ;;
    sonarr) echo 8989 ;;
    lidarr) echo 8686 ;;
    readarr) echo 8787 ;;
    prowlarr) echo 9696 ;;
    bazarr) echo 6767 ;;
    qbittorrent) echo "${WEBUI_PORT:-8080}" ;;
    *) return 1 ;;
  esac
}

# The app this container ships is whichever s6 service it defines.
preparr_detect_type() {
  local app
  for app in radarr sonarr lidarr readarr prowlarr bazarr qbittorrent; do
    if [[ -d "/etc/s6-overlay/s6-rc.d/svc-${app}" ]]; then
      echo "${app}"
      return 0
    fi
  done
  return 1
}

preparr_app_port() {
  local port=""
  if [[ -f /config/config.xml ]]; then
    port="$(sed -n 's:.*<Port>\([0-9]\+\)</Port>.*:\1:p' /config/config.xml | head -n1)"
  fi
  if [[ -z "${port}" ]]; then
    port="$(preparr_default_port "${SERVARR_TYPE:-}")" || return 1
  fi
  echo "${port}"
}

# Honour CONFIG_PATH when set, otherwise take the first config file that exists.
# "<app>-config.json" is the layout the upstream helm chart mounts.
preparr_resolve_config_path() {
  local candidate
  if [[ -n "${CONFIG_PATH:-}" ]]; then
    echo "${CONFIG_PATH}"
    return 0
  fi
  for candidate in \
    "/config/servarr.yaml" \
    "/config/servarr.yml" \
    "/config/servarr.json" \
    "/config/servarr.toml" \
    "/config/${SERVARR_TYPE:-servarr}-config.json" \
    "/config/preparr.json" \
    "/config/preparr.yaml"; do
    if [[ -f "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  echo "/config/servarr.yaml"
}

# LSIO containers tend to carry an uppercase LOG_LEVEL; PrepArr only accepts
# lowercase debug|info|warn|error and exits on anything else.
preparr_log_level() {
  case "$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')" in
    debug|trace|verbose) echo debug ;;
    warn|warning) echo warn ;;
    error|fatal|critical) echo error ;;
    *) echo info ;;
  esac
}

# Fill in the environment both modes share. Fails only when there is no app to
# configure and the user has not named one.
preparr_common_env() {
  if [[ -z "${SERVARR_TYPE:-}" ]]; then
    SERVARR_TYPE="$(preparr_detect_type)" || return 1
  fi
  export SERVARR_TYPE

  local port
  port="$(preparr_app_port)" || return 1

  CONFIG_PATH="$(preparr_resolve_config_path)"
  LOG_LEVEL="$(preparr_log_level)"
  export CONFIG_PATH LOG_LEVEL

  export SERVARR_URL="${SERVARR_URL:-http://localhost:${port}}"
  export SERVARR_CONFIG_PATH="${SERVARR_CONFIG_PATH:-/config/config.xml}"
  export LOG_FORMAT="${LOG_FORMAT:-json}"
  export BUN_RUNTIME_TRANSPILER_CACHE_DIR="${BUN_RUNTIME_TRANSPILER_CACHE_DIR:-${PREPARR_RUNTIME_DIR}/cache}"

  # qBittorrent and Bazarr are driven through their own URLs rather than SERVARR_URL.
  case "${SERVARR_TYPE:-}" in
    qbittorrent)
      export QBITTORRENT_URL="${QBITTORRENT_URL:-http://localhost:${port}}"
      PREPARR_WAIT_URL="${QBITTORRENT_URL}"
      ;;
    bazarr)
      export BAZARR_URL="${BAZARR_URL:-http://localhost:${port}}"
      PREPARR_WAIT_URL="${BAZARR_URL}"
      ;;
    *)
      PREPARR_WAIT_URL="${SERVARR_URL}"
      ;;
  esac
}

# PrepArr needs a password for the database, and for an admin account on
# everything except qBittorrent and Bazarr.
preparr_check_required_env() {
  local missing=()
  [[ -z "${POSTGRES_PASSWORD:-}" ]] && missing+=("POSTGRES_PASSWORD")
  case "${SERVARR_TYPE:-}" in
    qbittorrent|bazarr) ;;
    *) [[ -z "${SERVARR_ADMIN_PASSWORD:-}" ]] && missing+=("SERVARR_ADMIN_PASSWORD") ;;
  esac
  if [[ ${#missing[@]} -gt 0 ]]; then
    preparr_log "**** missing required environment: ${missing[*]} ****"
    return 1
  fi
}

preparr_wait_for_postgres() {
  local host="${POSTGRES_HOST:-localhost}"
  local port="${POSTGRES_PORT:-5432}"
  local user="${POSTGRES_USER:-${POSTGRES_USERNAME:-postgres}}"
  local timeout="${PREPARR_POSTGRES_TIMEOUT:-300}"
  local waited=0

  if ! command -v pg_isready >/dev/null 2>&1; then
    preparr_log "pg_isready is unavailable, leaving the wait to PrepArr's own retries"
    return 0
  fi

  preparr_log "waiting for postgres at ${host}:${port}"
  until pg_isready -h "${host}" -p "${port}" -U "${user}" >/dev/null 2>&1; do
    if (( waited >= timeout )); then
      preparr_log "postgres at ${host}:${port} was still unreachable after ${timeout}s"
      return 1
    fi
    sleep 2
    waited=$(( waited + 2 ))
  done
  preparr_log "postgres is ready"
}

# curl without -f returns 0 for any HTTP response, so a 401 counts as "up".
preparr_wait_for_app() {
  local url="$1"
  local timeout="${PREPARR_APP_TIMEOUT:-300}"
  local waited=0

  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi

  preparr_log "waiting for ${SERVARR_TYPE:-app} at ${url}"
  until curl -s -o /dev/null --max-time 5 "${url}"; do
    if (( waited >= timeout )); then
      preparr_log "${SERVARR_TYPE:-app} was still unreachable after ${timeout}s, starting anyway"
      return 1
    fi
    sleep 5
    waited=$(( waited + 5 ))
  done
}
