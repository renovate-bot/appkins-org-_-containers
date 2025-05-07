#!/usr/bin/env bash

docker build -t openbmc-rpi -f Dockerfile .
docker run --rm -it --name openbmc-rpi -v ./entrypoint.sh:/build/openbmc/entrypoint.sh --mount type=bind,source="$(pwd)"/build,target=/build/openbmc/out openbmc-rpi
