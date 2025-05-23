#!/usr/bin/env bash

set -ex
docker build --platform linux/amd64 -t devstack .
docker run --platform linux/amd64 --rm -it --name devstack devstack
