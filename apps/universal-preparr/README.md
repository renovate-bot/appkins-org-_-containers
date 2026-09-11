# preparr - Docker mod for the arr suite of containers

Runs [robbeverhelst/PrepArr](https://github.com/robbeverhelst/Preparr) inside the
app's own container, replacing the `preparr-init` and `preparr-sidecar` containers
from the upstream [helm chart](https://github.com/robbeverhelst/Preparr/blob/main/helm/preparr/templates/radarr.yaml).

* **init** runs as an s6 oneshot before the app starts: it provisions the
  PostgreSQL database and user, then writes `/config/config.xml`.
* **sidecar** runs as an s6 longrun alongside the app: it waits for the API,
  then watches the config file and reconciles the app through its API.

The mod carries its own `bun` (pulled from the official release zip at build time,
pinned by the `BUN_VERSION` build arg and checksum verified) plus PrepArr's `dist`
and `node_modules`, all under `/preparr`. It takes the musl build, so this mod
requires an Alpine based image - which covers every app PrepArr supports. On
anything else the mod says so and gets out of the way.

In any container docker arguments, set an environment variable `DOCKER_MODS=ghcr.io/appkins/universal-preparr:latest`

If adding multiple mods, enter them in an array separated by `|`, such as `DOCKER_MODS=ghcr.io/appkins/universal-preparr:latest|linuxserver/mods:universal-mod2`

## Required environment

| Name                    | Notes                                                     |
|-------------------------|-----------------------------------------------------------|
| `POSTGRES_PASSWORD`     | Always required                                            |
| `SERVARR_ADMIN_PASSWORD`| Required except for qBittorrent and Bazarr                 |

Without these the mod logs what is missing and gets out of the way - the app
still starts, the sidecar stays parked. The same applies to any other failure
during init: a mod should never keep its container from booting.

## Sidecar environment

| Name                        | Default                     |
|-----------------------------|-----------------------------|
| `CONFIG_PATH`               | first config file found (see below) |
| `CONFIG_WATCH`              | `true`                      |
| `CONFIG_RECONCILE_INTERVAL` | `60` (seconds)              |
| `HEALTH_PORT`               | `9001`                      |
| `LOG_LEVEL`                 | `info`                      |

`LOG_LEVEL` is lowercased and mapped onto PrepArr's `debug|info|warn|error`, so
the uppercase values other mods use are safe here.

When `CONFIG_PATH` is unset the mod takes the first of these that exists, falling
back to `/config/servarr.yaml`:

```
/config/servarr.{yaml,yml,json,toml}
/config/<app>-config.json          # the layout the helm chart's ConfigMap mounts
/config/preparr.{json,yaml}
```

## Detected for you

| Name                   | Default                                                        |
|------------------------|----------------------------------------------------------------|
| `SERVARR_TYPE`         | the app this container ships (`/etc/s6-overlay/s6-rc.d/svc-*`)  |
| `SERVARR_URL`          | `http://localhost:<port from /config/config.xml>`               |
| `SERVARR_CONFIG_PATH`  | `/config/config.xml`                                            |
| `QBITTORRENT_URL`      | `http://localhost:${WEBUI_PORT:-8080}` when the app is qBittorrent |
| `BAZARR_URL`           | `http://localhost:6767` when the app is Bazarr                  |

Recognised apps: radarr, sonarr, lidarr, readarr, prowlarr, bazarr, qbittorrent.
Set `SERVARR_TYPE` explicitly to override the detection - PrepArr cannot
auto-detect during init, since the app is not running yet.

Everything else PrepArr reads is passed straight through: `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_LOG_DATABASE_ENABLED`,
`SERVARR_ADMIN_USER`, `SERVARR_API_KEY`, `PROWLARR_URL`, `PROWLARR_API_KEY`, and
the rest of the [PrepArr environment](https://github.com/robbeverhelst/Preparr).

## Waiting

The mod replaces the chart's `wait-for-postgres` init container too: init blocks
on `pg_isready` for up to `PREPARR_POSTGRES_TIMEOUT` seconds (default `300`), and
the sidecar blocks on the app's API for up to `PREPARR_APP_TIMEOUT` seconds
(default `300`) before starting anyway and letting PrepArr retry.

## Example

```yaml
services:
  radarr:
    image: lscr.io/linuxserver/radarr:latest
    environment:
      DOCKER_MODS: ghcr.io/appkins/universal-preparr:latest
      POSTGRES_HOST: postgres
      POSTGRES_PASSWORD: postgres123
      SERVARR_ADMIN_PASSWORD: adminpass
      SERVARR_API_KEY: 2bac5d00dca43258313c734821a15c4c
      CONFIG_PATH: /config/radarr-config.json
      HEALTH_PORT: 9001
    volumes:
      - ./radarr-config.json:/config/radarr-config.json:ro
    ports: ["7878:7878", "9001:9001"]
```
