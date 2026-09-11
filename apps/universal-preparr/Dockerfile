# syntax=docker/dockerfile:1

FROM ghcr.io/robbeverhelst/preparr:0.19.7 AS app

FROM scratch

LABEL maintainer="appkins"

COPY --from=app --chown=0:0 /usr/local/bin/bun /preparr/bun
COPY --from=app --chown=0:0 /app/dist /preparr/dist
COPY --from=app --chown=0:0 /app/node_modules /preparr/node_modules

# copy local files
COPY root/ /
