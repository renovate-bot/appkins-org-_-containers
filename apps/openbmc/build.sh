#!/usr/bin/env bash

docker run --rm -it --name openbmc-build --oom-kill-disable --cpu-shares 4096 -v ./entrypoint.sh:/build/openbmc/entrypoint.sh --mount type=bind,source="$(pwd)"/build,target=/build/openbmc/out openbmc


./entrypoint.sh


--mount type=bind,source="$(pwd)"/build,target=/build/openbmc/build \
