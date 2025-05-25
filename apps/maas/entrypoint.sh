#!/usr/bin/env bash

LOG_TARGET="${LOG_TARGET:-console}"

systemctl="$(command -v systemctl)"

# CMD="$1"
# shift
# args=""
# if [ $# -gt 0 ]; then
#     args="$(printf "%q " "$@")"
# fi

CMD="$*"

# shellcheck source=/dev/null
. /etc/lsb-release


# if [ ! -e /var/lib/apt/lists ]; then
#     apt-get update
# fi

cat > /usr/local/bin/docker_commandline.sh <<EOF
#!/bin/bash
# Default environment variables

# Recreate the initial environment from docker run
$(export -p)

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"

if [[ "${POSTGRES_HOST}" != "$(maas-region local_config_get --database-host | cut -d' ' -f2)" ]]; then
  /usr/bin/systemctl stop maas-regiond
  /usr/sbin/maas-region local_config_set \
    --database-host "${POSTGRES_HOST}" \
    --database-name "${POSTGRES_DB:-maas}" \
    --database-pass "${POSTGRES_PASSWORD:-maas}" \
    --database-user "${POSTGRES_USER:-maas}"

  /usr/sbin/maas-region dbupgrade
  /usr/bin/systemctl restart bind9
  /usr/bin/systemctl start maas-regiond
fi

# Force these environment variables
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/etc/profile"

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
StandardInput=tty
StandardOutput=tty
StandardError=tty
WorkingDirectory=$PWD

[Install]
WantedBy=default.target
EOF

"$systemctl" enable docker-exec.service


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

exec /lib/systemd/systemd --system --log-target="${LOG_TARGET}" --system-unit docker-exec.service
