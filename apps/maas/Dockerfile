FROM ubuntu:noble

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=linux \
    TZ="America/Chicago" \
    MAAS_VERSION=3.6 \
    S6_OVERLAY_VERSION=3.2.1.0

RUN apt update -qq \
    && apt install -yq software-properties-common \
                       apt-utils \
                       xz-utils \
    && apt-add-repository -y ppa:maas/${MAAS_VERSION} \
    && apt update -qq \
    && apt install -yq bind9 bind9-libs bind9-utils dbconfig-common dbconfig-pgsql distro-info dns-root-data freeipmi-common \
                       freeipmi-tools gettext-base grub-common ibverbs-providers ieee-data iputils-ping isc-dhcp-server \
                       javascript-common libcares2 libdbi-perl libecap3 libefiboot1t64 libefivar1t64 libfreeipmi17 libfuse3-3 \
                       libibverbs1 libipmiconsole2 libipmidetect0 libjs-jquery liblmdb0 libltdl7 libnetfilter-conntrack3 \
                       libnfnetlink0 libnl-3-200 libnl-route-3-200 libnuma1 libpcap0.8t64 libtdb1 libvirt-clients \
                       libvirt-l10n libvirt0 libwrap0 libyajl2 maas-agent maas-cli maas-dhcp maas-netmon maas-proxy \
                       maas-rack-controller maas-region-api maas-region-controller ncurses-term openssh-server \
                       openssh-sftp-server os-prober postgresql postgresql-client pxelinux python3-aiodns python3-aiofiles \
                       python3-aiohttp python3-aiosignal python3-anyio python3-asgiref python3-async-timeout python3-asyncpg \
                       python3-django python3-django-maas python3-django-piston3 python3-ecdsa python3-fastapi \
                       python3-frozenlist python3-greenlet python3-h11 python3-itsdangerous python3-jinja2 python3-jose \
                       python3-markupsafe python3-mimeparse python3-multidict python3-multipart python3-netaddr \
                       python3-passlib python3-petname python3-psycopg2 python3-pycares python3-pydantic \
                       python3-pythonjsonlogger python3-requests-unixsocket python3-rsa python3-sniffio python3-sqlalchemy \
                       python3-sqlparse python3-starlette python3-structlog python3-temporalio python3-typeshed \
                       python3-uvicorn python3-wsproto python3-yarl squid squid-common squid-langpack ssh-import-id \
                       syslinux-common tcpdump temporal \
    && rm -rf /var/lib/apt/lists/* \
    && echo "maas ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY root/ /

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-x86_64.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-x86_64.tar.xz
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/syslogd-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/syslogd-overlay-noarch.tar.xz

# USER maas
# WORKDIR /maas

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
