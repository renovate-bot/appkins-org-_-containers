# syntax=docker/dockerfile:1

ARG RUST_VERSION=1.88
ARG VERSION=0.1.7

# The builder is pinned to the build platform and cross compiles. build-images.yaml
# builds each platform in its own job and never sets up QEMU, so nothing built for
# the target architecture may be executed during the build.
FROM --platform=${BUILDPLATFORM} rust:${RUST_VERSION}-bookworm AS builder

ARG BUILDKIT_SBOM_SCAN_STAGE=true \
    TARGETARCH \
    VERSION

WORKDIR /src

ADD https://github.com/Zariel/cleanrr/archive/refs/tags/v${VERSION}.tar.gz /cleanrr.tar.gz

RUN tar -xzf /cleanrr.tar.gz --strip-components=1 -C /src \
    && rm /cleanrr.tar.gz

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) target="x86_64-unknown-linux-gnu"; packages="" ;; \
      arm64) target="aarch64-unknown-linux-gnu"; packages="gcc-aarch64-linux-gnu g++-aarch64-linux-gnu libc6-dev-arm64-cross" ;; \
      *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    echo "${target}" > /rust-target; \
    apt-get update; \
    apt-get install --no-install-recommends --yes cmake ${packages}; \
    rm -rf /var/lib/apt/lists/*; \
    rustup target add "${target}"

# rustls pulls in aws-lc-sys and ring, which both compile C and assembly, so the
# cross toolchain has to be named explicitly. Unused when TARGETARCH is amd64.
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
    CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
    CXX_aarch64_unknown_linux_gnu=aarch64-linux-gnu-g++ \
    AR_aarch64_unknown_linux_gnu=aarch64-linux-gnu-ar

RUN --mount=type=cache,id=cleanrr-cargo-registry,target=/usr/local/cargo/registry \
    set -eux; \
    target="$(cat /rust-target)"; \
    cargo build --locked --release --target "${target}"; \
    install -m 0755 "target/${target}/release/cleanrr" /cleanrr

# distroless already carries ca-certificates and a nonroot user, so the final
# stage needs no RUN - which is what lets it be assembled for either platform
# from an amd64 builder.
FROM gcr.io/distroless/cc-debian12:nonroot

ARG VERSION \
    BUILD_DATE

COPY --from=builder /cleanrr /usr/local/bin/cleanrr

USER 65532:65532
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/local/bin/cleanrr"]

LABEL org.opencontainers.image.authors="Appkins <github-cleanrr@appkins.io>"
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.description="Safely remove stale blocked imports from Radarr and Sonarr queues"
LABEL org.opencontainers.image.documentation="https://github.com/appkins-org/containers/tree/main/apps/cleanrr"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/Zariel/cleanrr"
LABEL org.opencontainers.image.title="cleanrr"
LABEL org.opencontainers.image.url="https://github.com/appkins-org/containers"
LABEL org.opencontainers.image.vendor="Appkins <github-cleanrr@appkins.io>"
LABEL org.opencontainers.image.version=${VERSION}
