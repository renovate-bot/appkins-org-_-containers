# cleanrr

Container build for [Zariel/cleanrr](https://github.com/Zariel/cleanrr) - a small
service that removes stale, blocked imports from Radarr and Sonarr queues.

## Build

The binary is cross compiled from the build platform: this repo builds each
platform in a separate job without QEMU, so the builder stage is pinned with
`--platform=${BUILDPLATFORM}` and targets `x86_64`/`aarch64-unknown-linux-gnu`.
`rustls` pulls in `aws-lc-sys` and `ring`, which compile C and assembly, so the
cross toolchain is installed and named through the usual `CC_*`/`AR_*` variables.

The runtime stage is `gcr.io/distroless/cc-debian12:nonroot`, which already has
ca-certificates and an unprivileged user - so it needs no `RUN`, and can be put
together for either architecture from an amd64 builder.

| Build arg      | Default  |
|----------------|----------|
| `VERSION`      | `0.1.7`  |
| `RUST_VERSION` | `1.88`   |

```bash
docker build --platform linux/arm64 --build-arg VERSION=0.1.7 -t cleanrr apps/cleanrr
```

## Usage

Configuration is TOML at `./cleanrr.toml` (`CLEANRR_CONFIG` to move it), or
environment variables with the `CLEANRR_` prefix and `__` between nested keys:

```bash
docker run -p 8080:8080 \
  -e CLEANRR_MINIMUM_AGE=30m \
  -e CLEANRR_DRY_RUN=true \
  -e CLEANRR_SERVERS__MOVIES__URL=http://radarr:7878 \
  -e CLEANRR_SERVERS__MOVIES__API_KEY=... \
  -e CLEANRR_SERVERS__TV__URL=http://sonarr:8989 \
  -e CLEANRR_SERVERS__TV__API_KEY=... \
  ghcr.io/appkins-org/cleanrr:rolling
```

Server names are arbitrary and become Prometheus labels. Port 8080 serves
`/livez`, `/readyz`, `/health/{live,ready,startup}` and `/metrics`. Start with
`CLEANRR_DRY_RUN=true` and check the logs before letting it remove anything.

See the [upstream README](https://github.com/Zariel/cleanrr#readme) for the full
cleanup policy.
