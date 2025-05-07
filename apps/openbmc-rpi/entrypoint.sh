#!/usr/bin/env bash

sudo chown -R "$(id -u):$(id -g)" build
sudo chmod -R u+rw build

# cat <<EOF | tee ./meta-openpower/recipes-phosphor/cli/cli11_%.bbappend
# # Disable tests to avoid memory issues
# EXTRA_OECMAKE += "-DCLI11_TESTING=OFF"
# EOF

sed -i 's/machine: raspberrypi4/machine: raspberrypi4-64/g' meta-raspberrypi/kas-poky-rpi.yml

kas build meta-raspberrypi/kas-poky-rpi.yml
echo "Build complete - Install .wic.bz2 image to SD card"
