# flemarr - Docker mod for any container

## Custom environment configuration

This container assists in configuring arr applications [flemmarr/flemmarr](https://github.com/flemmarr/flemarr).

## Dynamic custom environment configuration

This mod adds common troubleshooting tools to any container, to be installed/updated during container start.

In any container docker arguments, set an environment variable `DOCKER_MODS=linuxserver/mods:universal-flemmarr`

If adding multiple mods, enter them in an array separated by `|`, such as `DOCKER_MODS=linuxserver/mods:universal-flemmarr|linuxserver/mods:universal-mod2`
