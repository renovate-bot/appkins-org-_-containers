#!/usr/bin/env bash

# Exit immediately if a command fails
set -e

# Make the script more verbose
[ "${DEBUG:-false}" = "true" ] && set -x

COMMAND="${*:-start}"

# Default configuration values
KEYSTONE_USER="${KEYSTONE_USER:-keystone}"
KEYSTONE_GROUP="${KEYSTONE_GROUP:-keystone}"
KEYSTONE_CONF_DIR="${KEYSTONE_CONF_DIR:-/etc/keystone}"
KEYSTONE_CONF="${KEYSTONE_CONF:-/etc/keystone/keystone.conf}"
KEYSTONE_DOMAIN="${OS_BOOTSTRAP_DOMAIN_NAME:-keystone}"
LOG_DIR="/var/log/keystone"

# Required environment variables check
function check_required_vars() {
  local required_vars=(
    "OS_BOOTSTRAP_PASSWORD"
  )

  for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
      echo "ERROR: Required environment variable $var is not set"
      return 1
    fi
  done
  return 0
}

# Setup directories and permissions
function setup_directories() {
  echo "Setting up Keystone directories..."

  # Create necessary directories with proper permissions
  for dir in domains fernet-keys credential-keys jws-keys/private jws-keys/public; do
    mkdir -p "${KEYSTONE_CONF_DIR}/${dir}"
    chown -R "${KEYSTONE_USER}:${KEYSTONE_GROUP}" "${KEYSTONE_CONF_DIR}/${dir}"
    chmod -R 0755 "${KEYSTONE_CONF_DIR}/${dir}"
  done

  # Create log directory
  mkdir -p "${LOG_DIR}"
  chown -R "${KEYSTONE_USER}:${KEYSTONE_GROUP}" "${LOG_DIR}"
  chmod -R 0755 "${LOG_DIR}"
}

# Apache setup
function setup_apache() {
  echo "Setting up Apache..."

  if [[ "$(whoami)" == 'root' ]]; then
    # Set Apache conf dir if not already set
    APACHE_CONFDIR="${APACHE_CONFDIR:-}"

    # Load Apache environment variables
    if [ -f /etc/apache2/envvars ]; then
      # shellcheck source=/dev/null
      source /etc/apache2/envvars
    else
      echo "WARNING: Apache envvars file not found"
    fi

    # Create and clean run directory
    install -d /var/run/apache2/
    rm -rf /var/run/apache2/*

    # Set ServerName to prevent Apache warnings
    if grep -q "ServerName" /etc/apache2/apache2.conf; then
      sed -i "s/ServerName.*/ServerName ${KEYSTONE_DOMAIN}/" /etc/apache2/apache2.conf
    else
      echo "ServerName ${KEYSTONE_DOMAIN}" >> /etc/apache2/apache2.conf
    fi

    # Configure Apache modules
    if [ -n "${A2DISMOD[*]}" ]; then
      for mod in "${A2DISMOD[@]}"; do
        a2dismod "${mod}" || echo "WARNING: Failed to disable Apache module: ${mod}"
      done
    fi

    if [ -n "${A2ENMOD[*]}" ]; then
      for mod in "${A2ENMOD[@]}"; do
        a2enmod "${mod}" || echo "WARNING: Failed to enable Apache module: ${mod}"
      done
    fi
  else
    echo "WARNING: Not running as root. Apache configuration may be incomplete."
  fi
}

# Generate crypto keys
function setup_crypto() {
  echo "Setting up cryptographic keys..."

  # JWS Keys
  if [ -f "${KEYSTONE_CONF_DIR}/jws-keys/private/private.pem" ]; then
    echo "JWS private key already exists, skipping generation."
  else
    echo "Generating JWS keypair..."
    keystone-manage --config-file "${KEYSTONE_CONF}" create_jws_keypair \
      --keystone-user "${KEYSTONE_USER}" \
      --keystone-group "${KEYSTONE_GROUP}" || {
        echo "ERROR: Failed to create JWS keypair"
        return 1
      }

    # Move keys if they were generated in the current directory
    for key_type in private public; do
      if [ -f "${key_type}.pem" ]; then
        echo "Moving ${key_type} key to proper location..."
        chown "${KEYSTONE_USER}:${KEYSTONE_GROUP}" "${key_type}.pem"
        chmod 0640 "${key_type}.pem"
        mv "${key_type}.pem" "${KEYSTONE_CONF_DIR}/jws-keys/${key_type}/"
      else
        echo "WARNING: ${key_type}.pem not found in current directory"
      fi
    done
  fi

  # Fernet token setup
  if [[ -f "${KEYSTONE_CONF_DIR}/fernet-keys/0" ]] && [[ -f "${KEYSTONE_CONF_DIR}/fernet-keys/1" ]]; then
    echo "Fernet keys already exist, skipping generation."
  else
    echo "Generating Fernet keys"
    keystone-manage --config-file "${KEYSTONE_CONF}" fernet_setup \
      --keystone-user "${KEYSTONE_USER}" \
      --keystone-group "${KEYSTONE_GROUP}" || {
        echo "WARNING: Fernet setup failed, tokens may not work correctly"
      }
  fi

  # Token setup
  keystone-manage --config-file "${KEYSTONE_CONF}" token_setup \
    --keystone-user "${KEYSTONE_USER}" \
    --keystone-group "${KEYSTONE_GROUP}" || {
      echo "ERROR: Token setup failed"
      return 1
    }

  # Credential setup
  if [[ -f "${KEYSTONE_CONF_DIR}/credential-keys/0" ]] && [[ -f "${KEYSTONE_CONF_DIR}/credential-keys/1" ]]; then
    echo "Credential key already exists, skipping generation."
  else
    echo "Setting up credentials..."
    keystone-manage --config-file "${KEYSTONE_CONF}" credential_setup \
      --keystone-user "${KEYSTONE_USER}" \
      --keystone-group "${KEYSTONE_GROUP}" || {
        echo "ERROR: Credential setup failed"
        return 1
      }
  fi

  return 0
}

# Database initialization
function setup_database() {
  IS_DB_SYNCED=$(redis_get keystone:dbsynced)
  echo "Checking Keystone DB sync status: ${IS_DB_SYNCED}"

  if [ "${IS_DB_SYNCED}" == "true" ]; then
    SKIP_KEYSTONE_DB_SYNC=true
  fi

  if [ -z "${SKIP_KEYSTONE_DB_SYNC}" ]; then
    echo "Syncing database schema..."
    keystone-manage --config-file "${KEYSTONE_CONF}" db_sync || {
      echo "ERROR: Database sync failed"
      return 1
    }
    redis_set keystone:dbsynced "true" || {
      echo "ERROR: Failed to set Keystone DB sync status in Redis"
      return 1
    }
  else
    echo "Skipping database sync as SKIP_KEYSTONE_DB_SYNC is set"
  fi

  return 0
}

# Bootstrap Keystone
function bootstrap_keystone() {
  IS_BOOTSTRAPPED=$(redis_get keystone:bootstrapped)
  echo "Checking Keystone bootstrap status: ${IS_BOOTSTRAPPED}"

  if [ "${IS_BOOTSTRAPPED}" == "true" ]; then
    echo "Keystone has already been bootstrapped, skipping..."
    return 0
  fi

  if [ -z "${SKIP_KEYSTONE_BOOTSTRAP}" ]; then
    echo "Bootstrapping Keystone..."
    keystone-manage --config-file="${KEYSTONE_CONF}" bootstrap \
      --bootstrap-role-name "${OS_BOOTSTRAP_ROLE_NAME:-admin}" \
      --bootstrap-username "${OS_BOOTSTRAP_USERNAME:-admin}" \
      --bootstrap-password "${OS_BOOTSTRAP_PASSWORD:-password}" \
      --bootstrap-project-name "${OS_BOOTSTRAP_PROJECT_NAME}:-admin" \
      --bootstrap-admin-url "${OS_BOOTSTRAP_ADMIN_URL:-http://127.0.0.1:35357}" \
      --bootstrap-public-url "${OS_BOOTSTRAP_PUBLIC_URL:-http://127.0.0.1:5000}" \
      --bootstrap-internal-url "${OS_BOOTSTRAP_INTERNAL_URL:-http://127.0.0.1:5000}" \
      --bootstrap-region-id "${OS_BOOTSTRAP_REGION_ID:-RegionOne}" || {
        echo "ERROR: Keystone bootstrap failed"
        return 1
      }

    redis_set keystone:bootstrapped "true" || {
      echo "ERROR: Failed to set Keystone bootstrap status in Redis"
      return 1
    }

    echo "Keystone bootstrap completed successfully"
  else
    echo "Skipping Keystone bootstrap as SKIP_KEYSTONE_BOOTSTRAP is set"
  fi

  return 0
}

# Create service project and roles
function create_service_resources() {
  echo "Setting up service resources..."

  # Wait for Keystone to be responsive
  echo "Waiting for Keystone API to become available..."
  local max_retries=10
  local retry=0
  local status=1

  # Generate admin credentials
  export OS_USERNAME="${OS_BOOTSTRAP_USERNAME:-admin}"
  export OS_PASSWORD="${OS_BOOTSTRAP_PASSWORD:-password}"
  export OS_PROJECT_NAME="${OS_BOOTSTRAP_PROJECT_NAME:-admin}"
  export OS_USER_DOMAIN_NAME="Default"
  export OS_PROJECT_DOMAIN_NAME="Default"
  export OS_AUTH_URL="http://127.0.0.1:5000/identity/v3"
  export OS_IDENTITY_API_VERSION=3

  # Attempt to use openstack command with admin credentials
  while [ $status -ne 0 ] && [ $retry -lt $max_retries ]; do
    openstack token issue > /dev/null 2>&1
    status=$?

    if [ $status -ne 0 ]; then
      echo "Keystone not ready yet, retrying in 5 seconds... (attempt $((retry+1))/$max_retries)"
      sleep 5
      ((retry++))
    fi
  done

  if [ $status -ne 0 ]; then
    echo "ERROR: Keystone API did not become available after $max_retries retries"
    return 1
  fi

  # Create service project if it doesn't exist
  if ! openstack project show service &>/dev/null; then
    echo "Creating service project..."
    openstack project create --domain default --description "Service Project" service || {
      echo "ERROR: Failed to create service project"
      return 1
    }
  else
    echo "Service project already exists"
  fi

  # Create service role if it doesn't exist
  if ! openstack role show service &>/dev/null; then
    echo "Creating service role..."
    openstack role create service || {
      echo "ERROR: Failed to create service role"
      return 1
    }
  else
    echo "Service role already exists"
  fi

  # Create reader role if it doesn't exist (needed for application credentials)
  if ! openstack role show reader &>/dev/null; then
    echo "Creating reader role..."
    openstack role create reader || {
      echo "ERROR: Failed to create reader role"
      return 1
    }
  else
    echo "Reader role already exists"
  fi

  return 0
}

function redis_set() {
  local key="$1"
  local value="$2"
  python -c 'print(__import__("redis").Redis(host="redis", port=6379, db=0, decode_responses=True).set("'"${key}"'", "'"${value}"'"))'
}

function redis_get() {
  local key="$1"
  python -c 'print(__import__("redis").Redis(host="redis", port=6379, db=0, decode_responses=True).get("'"${key}"'"))'
}

function create_services() {
  echo "Setting up applications..."
  # Check if we have required variables
  if [ -z "${SERVICES}" ]; then
    echo "Skipping creation of services (SERVICES not set)"
    return 0
  fi

  IFS=',' read -ra services_array <<< "$SERVICES"
  for service in "${services_array[@]}"; do
    IFS=':' read -r service_name service_desc service_domain service_type <<< "${service}"

    if ! openstack service show "${service_type}" &>/dev/null; then
      printf 'Creating service: %s\n\t%s\n\t%s\n\t%s\n' "${service_name}" "${service_desc}" "${service_domain}" "${service_type}"
      openstack service create --name "${service_name}" --description "${service_desc}" "${service_type}" || {
        echo "ERROR: Failed to create service ${service_name}"
      }
    else
      echo "Service ${service_name} already exists"
    fi

    endpoint_result="$(openstack endpoint show "${service_name}" 2>&1)"
    if [[ "${endpoint_result}" == "More than one endpoint exists"* ]]; then
      echo "Endpoint for service ${service_name} already exists"
    else
      # Create endpoints for the service
      openstack endpoint create --region RegionOne \
          "${service_name}" admin "https://${service_domain}"
      openstack endpoint create --region RegionOne \
          "${service_name}" public "https://${service_domain}"
      openstack endpoint create --region RegionOne \
          "${service_name}" internal "https://${service_domain}"
    fi
  done
}

function create_application_credentials() {
  echo "Setting up applications..."
  # Check if we have required variables
  if [ -z "${APPLICATION_CREDENTIALS}" ]; then
    echo "Skipping creation of application credentials (APPLICATION_CREDENTIALS not set)"
    return 0
  fi

  IFS=',' read -ra app_cred_array <<< "${APPLICATION_CREDENTIALS}"
  for app_cred in "${app_cred_array[@]}"; do
    IFS=':' read -r app_cred_name app_cred_secret app_cred_desc <<< "${app_cred}"
    if ! openstack application credential show "${app_cred_name}" &>/dev/null; then
      if [[ $(openstack application credential create --secret "${app_cred_secret}" \
        --role admin \
        --unrestricted \
        --description "${app_cred_desc}" "${app_cred_name}") ]]; then
          echo "Application credential ${app_cred_name} created successfully";
        else
          echo "ERROR: Failed to create application credential ${app_cred_name}"
        fi
    fi

    done
}

# Full management function
function manage() {
  # Ensure directories are set up
  setup_directories || return 1

  # Apply custom logging configuration if provided
  if [ -f /tmp/logging.conf ]; then
    cp /tmp/logging.conf "${KEYSTONE_CONF_DIR}/logging.conf"
    chown "${KEYSTONE_USER}:${KEYSTONE_GROUP}" "${KEYSTONE_CONF_DIR}/logging.conf"
    chmod 660 "${KEYSTONE_CONF_DIR}/logging.conf"
  fi

  # Set up cryptographic keys
  setup_crypto || { echo "ERROR: Keystone setup crypto failed"; }

  # Initialize database
  setup_database || { echo "ERROR: Keystone database setup failed"; }

  # Bootstrap Keystone
  bootstrap_keystone || { echo "ERROR: Keystone bootstrap failed"; }
}

# Start function
function start() {
  echo "Starting Keystone..."

  # Install additional Python packages if needed
  if [ -d "/var/lib/openstack/bin" ] && [ -f "/var/lib/openstack/bin/activate" ]; then
    echo "Installing additional Python packages..."
    # shellcheck source=/dev/null
    source "/var/lib/openstack/bin/activate"
    pip install redis pg8000
    deactivate
  fi

  # Check required environment variables
  check_required_vars || {
    echo "ERROR: Missing required environment variables"
  }

  # Set up Apache
  setup_apache || {
    echo "ERROR: Apache setup failed"
  }

  # Run management tasks
  if [ -z "${SKIP_KEYSTONE_MANAGE}" ]; then
    manage || {
      echo "ERROR: Keystone management failed"
    }
  else
    echo "Skipping Keystone management as SKIP_KEYSTONE_MANAGE is set"
  fi

  # Start Apache as daemon
  echo "Starting Apache as daemon..."
  /usr/sbin/apachectl start

  # Wait for Keystone to become available
  echo "Waiting for Keystone to become available..."
  sleep 5

  # Create service resources
  create_service_resources || {
    echo "WARNING: Failed to create service resources"
  }

  # Create service resources
  create_services || {
    echo "WARNING: Failed to create service resources"
  }

  create_application_credentials || {
    echo "WARNING: Failed to create application credentials"
  }

  # Setup signal handler for graceful shutdown
  trap_signals() {
    echo "Received shutdown signal, stopping Apache gracefully..."
    /usr/sbin/apachectl -k graceful-stop
    exit 0
  }

  # Trap SIGTERM and other signals
  trap trap_signals SIGTERM SIGINT SIGHUP

  echo "Apache is running as daemon. Waiting for signals..."

  # Keep the container running
  while true; do
    sleep 1
  done
}

# Stop function
function stop() {
  echo "Stopping Keystone..."

  if [ -f /etc/apache2/envvars ]; then
    # Loading Apache2 ENV variables
    # shellcheck source=/dev/null
    source /etc/apache2/envvars
  fi

  /usr/sbin/apachectl -k graceful-stop
}

# Help function
function help() {
  echo "Usage: $0 [start|stop|manage]"
  echo ""
  echo "Commands:"
  echo "  start   - Start Keystone service (default if no command specified)"
  echo "  stop    - Stop Keystone service"
  echo "  manage  - Run management tasks only without starting the service"
  echo "  help    - Display this help message"
}

# Main command handler
case "$COMMAND" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  manage)
    manage
    ;;
  help)
    help
    ;;
  *)
    echo "Unknown command: $COMMAND"
    help
    exit 1
    ;;
esac
