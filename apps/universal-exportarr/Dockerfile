# syntax=docker/dockerfile:1

FROM ghcr.io/onedr0p/exportarr:latest as app

FROM scratch

LABEL maintainer="appkins"

COPY --from=app /exportarr /app/exportarr/

# copy local files
COPY root/ /
