#!/usr/bin/env bash

sudo chown -R "$(id -u):$(id -g)" build
sudo chmod -R u+rw build

# cat <<EOF | tee ./meta-openpower/recipes-phosphor/cli/cli11_%.bbappend
# # Disable tests to avoid memory issues
# EXTRA_OECMAKE += "-DCLI11_TESTING=OFF"
# EOF

sed -i '/^# Limit parallel jobs/,/^PTEST_ENABLED_pn-cli11/!{
  /^$/a\
# Limit parallel jobs to reduce memory usage\
BB_NUMBER_THREADS = "4"\
PARALLEL_MAKE = "-j 4"\
\
# Skip tests for CLI11\
PTEST_ENABLED_pn-cli11 = "0"
  ; t
}' build/x570d4u/conf/local.conf

. setup x570d4u
bitbake obmc-phosphor-image
