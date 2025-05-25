FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=linux \
    TZ="America/Chicago" \
    MAAS_VERSION=3.6 \
    S6_OVERLAY_VERSION=3.2.1.0

RUN \
  apt update -qqqq && \
  apt install -yq --no-install-recommends software-properties-common apt-utils && \
  apt-add-repository -y ppa:maas/${MAAS_VERSION} && \
  apt update -qqqq && \
  apt install -yq --no-install-recommends \
    xz-utils \
    sudo \
    maas-region-api \
    maas-rack-controller && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  echo "maas ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY root/ /

ARG TARGETARCH
ENV TARGETARCH=${TARGETARCH}

RUN wget "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" -O "/tmp/s6-overlay-noarch.tar.xz" && \
    tar -C / -Jxpf "/tmp/s6-overlay-noarch.tar.xz" && \
    rm -f "/tmp/s6-overlay-noarch.tar.xz"
SHELL ["/bin/bash", "-c"]
RUN if [[ "${TARGETARCH}" == "arm64" ]]; then S6_ARCHIVE="s6-overlay-aarch64.tar.xz"; else S6_ARCHIVE="s6-overlay-x86_64.tar.xz"; fi && \
    wget "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/${S6_ARCHIVE}" -O "/tmp/${S6_ARCHIVE}" && \
    tar -C / -Jxpf "/tmp/${S6_ARCHIVE}" && \
    rm -f "/tmp/${S6_ARCHIVE}"

# add s6 optional syslogd
# ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/syslogd-overlay-noarch.tar.xz /tmp
# RUN tar -C / -Jxpf /tmp/syslogd-overlay-noarch.tar.xz

ENTRYPOINT ["/init"]
