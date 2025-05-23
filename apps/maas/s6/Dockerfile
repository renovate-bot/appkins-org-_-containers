FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=linux \
    TZ="America/Chicago" \
    MAAS_VERSION=3.6 \
    S6_OVERLAY_VERSION=3.2.1.0

RUN \
  apt update -qq && \
  apt install -yq software-properties-common \
    xz-utils \
    sudo \
    apt && \
  apt-add-repository -y ppa:maas/${MAAS_VERSION} && \
  apt update -qq && \
  apt install -yq --no-install-recommends \
    maas-rack-controller \
    maas-region-controller \
    maas-agent \
    maas-cli

COPY root/ /

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-aarch64.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-aarch64.tar.xz

# add s6 optional symlinks
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-symlinks-noarch.tar.xz && unlink /usr/bin/with-contenv
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-arch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-symlinks-arch.tar.xz

# add s6 optional syslogd
# ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/syslogd-overlay-noarch.tar.xz /tmp
# RUN tar -C / -Jxpf /tmp/syslogd-overlay-noarch.tar.xz

RUN \
  echo "**** Ripped from Ubuntu Docker Logic ****" && \
  rm -f /etc/apt/sources.list.d/ubuntu.sources && \
  set -xe && \
  echo '#!/bin/sh' \
    > /usr/sbin/policy-rc.d && \
  echo 'exit 101' \
    >> /usr/sbin/policy-rc.d && \
  chmod +x \
    /usr/sbin/policy-rc.d && \
  dpkg-divert --local --rename --add /sbin/initctl && \
  cp -a \
    /usr/sbin/policy-rc.d \
    /sbin/initctl && \
  sed -i \
    's/^exit.*/exit 0/' \
    /sbin/initctl && \
  echo 'force-unsafe-io' \
    > /etc/dpkg/dpkg.cfg.d/docker-apt-speedup && \
  echo 'DPkg::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' \
    > /etc/apt/apt.conf.d/docker-clean && \
  echo 'APT::Update::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' \
    >> /etc/apt/apt.conf.d/docker-clean && \
  echo 'Dir::Cache::pkgcache ""; Dir::Cache::srcpkgcache "";' \
    >> /etc/apt/apt.conf.d/docker-clean && \
  echo 'Acquire::Languages "none";' \
    > /etc/apt/apt.conf.d/docker-no-languages && \
  echo 'Acquire::GzipIndexes "true"; Acquire::CompressionTypes::Order:: "gz";' \
    > /etc/apt/apt.conf.d/docker-gzip-indexes && \
  echo 'Apt::AutoRemove::SuggestsImportant "false";' \
    > /etc/apt/apt.conf.d/docker-autoremove-suggests && \
  mkdir -p /run/systemd && \
  echo 'docker' \
    > /run/systemd/container && \
  echo "**** install apt-utils and locales ****" && \
  apt update -qq && \
  apt install -yq --no-install-recommends \
    apt && \
  echo "**** maas user ****" && \
  echo "maas ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
  echo "**** generate locale ****" && \
  locale-gen en_US.UTF-8 && \
  echo "**** cleanup ****" && \
  userdel ubuntu && \
  apt-get autoremove && \
  apt-get clean && \
  rm -rf \
    /tmp/* \
    /var/lib/apt/lists/* \
    /var/tmp/* \
    /var/log/*

ENTRYPOINT ["/init"]

# RUN apt install apt-utils software-properties-common -y

# RUN echo "${TZ}" > /etc/timezone && \
#         ln -fs "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
#         apt update -qq && \
#         apt install -yq git file wget sudo locales python3 python3-pip \
#         rm -rf /var/lib/apt/lists/* && \
#         locale-gen en_US.UTF-8

# # Set environment variables for locale using the new format
# ENV LANG=en_US.UTF-8 \
#     LANGUAGE=en_US:en \
#     LC_ALL=en_US.UTF-8

# RUN locale

# RUN echo "maas ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# RUN groupadd maas -g 1028
# RUN useradd -ms /bin/bash -p build build -u 1028 -g 1028 && \
#         usermod -aG sudo build && \
#         echo "maas:maas" | chpasswd

# RUN apt-add-repository -y ppa:maas/3.6 && apt update -qq && \
#         apt install -yq maas && \
#         rm -rf /var/lib/apt/lists/*

# USER maas
# WORKDIR /maas

# ENTRYPOINT ["/bin/bash"]
