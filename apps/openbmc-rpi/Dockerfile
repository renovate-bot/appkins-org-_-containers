FROM ubuntu:24.10

ENV DEBIAN_FRONTEND=noninteractive \
    TERM=linux \
    TZ="America/Chicago"

RUN apt-get update --fix-missing && apt-get -y upgrade

RUN apt-get install apt-utils software-properties-common -y

RUN echo "${TZ}" > /etc/timezone && \
        ln -fs "/usr/share/zoneinfo/${TZ}" /etc/localtime && \
        apt-get update && \
        apt-get install -yq \
        git gcc-14 g++-14 make file wget sudo lz4 ninja-build \
        build-essential chrpath cpio debianutils diffstat file \
        gawk gcc git iputils-ping libacl1 liblz4-dev locales \
        python3 python3-git python3-jinja2 python3-pexpect python3-pip \
        python3-subunit socat texinfo unzip wget xz-utils zstd \
        g++-14-arm-linux-gnueabi gcc-14-arm-linux-gnueabi cmake kas && \
        rm -rf /var/lib/apt/lists/* && \
        locale-gen en_US.UTF-8

# g++-14-multilib gcc-14-multilib && \

# Set environment variables for locale using the new format
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

RUN locale

RUN echo "build ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

RUN groupadd build -g 1028
RUN useradd -ms /bin/bash -p build build -u 1028 -g 1028 && \
        usermod -aG sudo build && \
        echo "build:build" | chpasswd

USER build
WORKDIR /build
RUN git config --global user.email "build@example.com" && git config --global user.name "Build"
RUN git clone https://github.com/openbmc/openbmc /build/openbmc && \
        cd openbmc && \
        git checkout master
WORKDIR /build/openbmc
RUN cd /build/openbmc && \
    mkdir -p .build

VOLUME /build/openbmc/build

ENTRYPOINT ["/bin/bash"]

# mkdir -p out
# docker run --rm -it --name openbmc-build -v ./out:/build/openbmc/out openbmc

# RUN \
#   . setup x570d4u out && \
#   . conf/local.conf && \
#   . conf/machine/include/aspeed.inc && \
#   . conf/machine/include/$(MACHINE).inc && \
#   bitbake obmc-phosphor-image


# x570d4u
# KMACHINE = "aspeed"
