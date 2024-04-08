# envsubst - Docker mod for any container

## Custom environment configuration

This container support setting certain custom enviroment variables with the use of [drone/envsubst](https://github.com/drone/envsubst).

| Name             | Default                    |
|------------------|----------------------------|
| ENVSUBST_TARGET  | `/config/config.xml`       |
| ENVSUBST_SOURCE  | `${ENVSUBST_TARGET}.tmpl`  |

## Dynamic custom environment configuration

This mod adds common troubleshooting tools to any container, to be installed/updated during container start.

In any container docker arguments, set an environment variable `DOCKER_MODS=linuxserver/mods:universal-envsubst`

If adding multiple mods, enter them in an array separated by `|`, such as `DOCKER_MODS=linuxserver/mods:universal-envsubst|linuxserver/mods:universal-mod2`
