ARG BASE_OS=noble
# Prepare the filesystem to copy into a blank image
FROM ubuntu:${BASE_OS}

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=linux \
    TZ="America/Chicago" \
    MAAS_VERSION=3.6

RUN apt update -qq \
    && apt install -yq --no-install-recommends \
           software-properties-common \
           apt-utils \
           xz-utils \
           sudo \
           systemd \
    && dpkg-divert --local --rename --add /sbin/udevadm \
    && ln -s /bin/true /sbin/udevadm \
    && apt-add-repository -y ppa:maas/${MAAS_VERSION} \
    && apt update -qq \
    && apt install -yq maas-region-api maas-rack-controller \
    && systemctl set-default multi-user.target \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "maas ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN \
    systemctl disable chrony && \
    systemctl enable maas-regiond.service && \
    systemctl enable maas-apiserver.service && \
    systemctl enable maas-temporal.service && \
    systemctl enable maas-temporal-worker.service


# Set the proper environment.
ENV container=docker \
	  init=/lib/systemd/systemd \
    PATH="$PATH:/etc/profile"

# Add our entrypoint
ADD entrypoint.sh /bin/

# Ensure docker sends the shutdown signal that systemd expects
STOPSIGNAL SIGRTMIN+3

# Set our entrypoint
ENTRYPOINT ["/bin/entrypoint.sh"]

# Set our default command
CMD ["/usr/bin/journalctl", "-f"]
