#!/bin/sh
DEBIAN_FRONTEND=noninteractive sudo apt-get -qqy update || sudo dnf update -qy
DEBIAN_FRONTEND=noninteractive sudo apt-get install -qqy git || sudo dnf install -qy git
sudo chown stack:stack /home/stack
cd /home/stack
git clone https://opendev.org/openstack/devstack
cd devstack
echo '[[local|localrc]]' > local.conf
echo ADMIN_PASSWORD=password >> local.conf
echo DATABASE_PASSWORD=password >> local.conf
echo RABBIT_PASSWORD=password >> local.conf
echo SERVICE_PASSWORD=password >> local.conf
./tools/create-stack-user.sh
./stack.sh
