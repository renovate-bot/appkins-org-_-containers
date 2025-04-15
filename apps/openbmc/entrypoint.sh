#!/usr/bin/env bash

sudo chown -R "$(id -u):$(id -g)" build
sudo chmod -R u+rw build

. setup x570d4u
bitbake obmc-phosphor-image
