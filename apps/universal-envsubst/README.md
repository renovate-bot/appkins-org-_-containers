# envsubst - Docker mod for any container

This mod adds common troubleshooting tools to any container, to be installed/updated during container start.

In any container docker arguments, set an environment variable `DOCKER_MODS=linuxserver/mods:universal-envsubst`

If adding multiple mods, enter them in an array separated by `|`, such as `DOCKER_MODS=linuxserver/mods:universal-envsubst|linuxserver/mods:universal-mod2`

Environment variables:

```bash
ENVSUBST_TARGET="/config/config.xml"
ENVSUBST_SOURCE="${ENVSUBST_TARGET}.tmpl"
```
