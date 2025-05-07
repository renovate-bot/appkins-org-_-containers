#syntax=docker/dockerfile:1

FROM debian:stable-slim

ARG BUILDKIT_SBOM_SCAN_CONTEXT=true \
    BUILDKIT_SBOM_SCAN_STAGE=true \
    TARGETPLATFORM \
    VERSION \
    BUILD_DATE

ENV VERSION=${VERSION} \
    DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,id=ser2net-apt-lists-${TARGETPLATFORM},target=/var/lib/apt/lists \
    --mount=type=cache,id=ser2net-apt-cache-${TARGETPLATFORM},target=/var/cache/apt \
    set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tini \
        ser2net \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["tini", "--", "ser2net", "-d", "-l", "-c", "/etc/ser2net.yaml"]

LABEL org.opencontainers.image.authors="Appkins <github-ser2net@appkins.io>"
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.description="Ser2net on Docker"
LABEL org.opencontainers.image.documentation="https://github.com/appkins-org/containers/tree/main/apps/ser2net"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/appkins-org/containers"
LABEL org.opencontainers.image.title="Ser2net on Docker"
LABEL org.opencontainers.image.url="https://github.com/appkins-org/containers"
LABEL org.opencontainers.image.vendor="Appkins <github-ser2net@appkins.io>"
LABEL org.opencontainers.image.version=${VERSION}
