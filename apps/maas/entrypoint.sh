#!/usr/bin/env bash

echo "Starting MAAS entrypoint script..."

LOG_TARGET="${LOG_TARGET:-console}"

systemctl="$(command -v systemctl)"

CMD="$*"
if [ -z "$CMD" ]; then
  CMD="while true; do sleep 30; done;"
fi

# shellcheck source=/dev/null
. /etc/lsb-release

MAAS_USER="${MAAS_USER:-admin}"
MAAS_PASSWORD="${MAAS_PASSWORD:-maasadmin}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_DB="${POSTGRES_DB:-maas}"
POSTGRES_USER="${POSTGRES_USER:-maas}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-maas}"
MAAS_URL="${MAAS_URL:-http://localhost:5240/MAAS}"

echo "Using POSTGRES_HOST: ${POSTGRES_HOST}"
if [[ ! -f /etc/maas/regiond.conf ]]; then
  echo "No /etc/maas/regiond.conf found, creating default configuration"
  mkdir -p /etc/maas
  chown -R maas:maas /etc/maas
  printf 'database_host: %s\ndatabase_name: %s\ndatabase_pass: %s\ndatabase_user: %s\nmaas_url: %s\n' \
    "${POSTGRES_HOST}" "${POSTGRES_DB}" "${POSTGRES_PASSWORD}" "${POSTGRES_USER}" "${MAAS_URL}" > /etc/maas/regiond.conf
  chmod 640 /etc/maas/regiond.conf
  chown maas:maas /etc/maas/regiond.conf
  echo "Created /etc/maas/regiond.conf with default values"
fi

if [[ "${POSTGRES_HOST}" != "$(maas-region local_config_get --database-host --plain)" ]]; then
  /usr/sbin/maas-region local_config_set \
    --database-host "${POSTGRES_HOST}" \
    --database-name "${POSTGRES_DB:-maas}" \
    --database-pass "${POSTGRES_PASSWORD:-maas}" \
    --database-user "${POSTGRES_USER:-maas}"
fi

/usr/sbin/maas-region dbupgrade

/usr/sbin/maas-region createadmin \
  --username "${MAAS_USER}" \
  --password "${MAAS_PASSWORD}" \
  --email "${MAAS_USER}@maas" \
  --ssh-import "gh:appkins" || true

cat > /usr/local/bin/docker_commandline.sh <<EOF
#!/bin/bash
# Default environment variables

# Recreate the initial environment from docker run
$(export -p)

# Force these environment variables
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/etc/profile"

MAAS_URL="\$(/usr/sbin/maas-region local_config_get --maas-url --plain)
API_KEY="\$(/usr/sbin/maas-region apikey --username "\${MAAS_USER}")"
PROFILE="\${MAAS_USER}"
maas login \$PROFILE \$MAAS_URL "\${API_KEY}"

# Run the command
echo "Executing: '${CMD}'"
sh -c "${CMD}" || exit \$?

/bin/systemctl exit \$?
EOF
chmod +x /usr/local/bin/docker_commandline.sh

cat > /etc/systemd/system/docker-exec.service <<EOF
[Unit]
Description=Docker commandline
Wants=maas-regiond.service
After=maas-regiond.service

[Service]
ExecStart=/usr/local/bin/docker_commandline.sh
Environment="LANG=en_US.UTF-8"
Restart=no
Type=oneshot
WorkingDirectory=$PWD

[Install]
WantedBy=default.target
EOF

"$systemctl" enable docker-exec.service &> /dev/null

rm /var/log/maas/*.log

ln -s /dev/stdout /var/log/maas/maas.log
ln -s /dev/stdout /var/log/maas/regiond.log
ln -s /dev/stdout /var/log/maas/rackd.log

# The presence of either .dockerenv or /run/.containerenv cause maas to
# incorrectly stage more than it should (e.g. libc and systemd). Remove them.
if [ -f /.dockerenv ]; then
    rm -f /.dockerenv
fi
if [ -f /run/.containerenv ]; then
    umount /run/.containerenv
    rm -f /run/.containerenv
fi

if grep -q securityfs /proc/filesystems; then
    mount -o rw,nosuid,nodev,noexec,relatime securityfs -t securityfs /sys/kernel/security
fi

if [ ! -d /run ]; then
  mount -t tmpfs tmpfs /run
fi

if [ ! -d /run/lock ]; then
  mkdir /run/lock
  mount -t tmpfs tmpfs /run/lock
fi

if [ -f /tmp/regiond.conf ]; then
  cp /tmp/regiond.conf /etc/maas/regiond.conf
else
  echo "No regiond.conf found in /tmp, using default configuration"
fi

{ journalctl -f > /dev/stdout || exit $?; } &

exec /lib/systemd/systemd \
  --system \
  --no-pager \
  --system-unit docker-exec.service
