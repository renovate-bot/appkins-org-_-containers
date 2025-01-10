#!/bin/bash

# This files contain environment variables with .ko files required for iptables
# support. For some reason it's not loaded by default. The other weird thing
# is that the .ko-files can't be loaded directly using insmod

IPTABLES_MODULE_LIST="/usr/syno/etc/iptables_modules_list"

# Binary that allows loading iptables kernel modules
SYNOMODULETOOL="/usr/syno/bin/synomoduletool"

SERVICE_NAME="ContainerManager"

MODULES_DIR="/lib/modules"
TUN_MODULE="${MODULES_DIR}/tun.ko"
WG_MODULE="${MODULES_DIR}/wireguard.ko"

DSM_VERSION="${DSM_VERSION:-7.2}"
ARCH="${ARCH:-v1000}"

KERNEL_MOD_URL="https://raw.githubusercontent.com/gpopesc/wireguard-module-synology/refs/heads/main/${DSM_VERSION}/${ARCH}.ko"

if [ ! -f "${WG_MODULE}" ]; then
    echo "WireGuard module not found, downloading..."
    curl -sfL -o "${WG_MODULE}" "${KERNEL_MOD_URL}"
fi

. "${IPTABLES_MODULE_LIST}"
if [ -x "$SYNOMODULETOOL" ] && [ -f "$IPTABLES_MODULE_LIST" ]; then
    sysctl -w net.ipv4.ip_forward=1

    for mod in ${KERNEL_MODULES_CORE} ${KERNEL_MODULES_NAT}; do
      lsmod | grep "${mod%.ko}" || {
        echo "Loading ${mod%.ko}..."
         "$SYNOMODULETOOL" --insmod "$SERVICE_NAME" "${mod}"
      }
    done
fi

/sbin/lsmod | grep "wireguard" || {
  echo "Loading wireguard.ko..."
  /sbin/insmod "${WG_MODULE}"
}

/sbin/lsmod | grep "tun" || {
  echo "Loading tun.ko..."
  /sbin/insmod "${TUN_MODULE}"
}
