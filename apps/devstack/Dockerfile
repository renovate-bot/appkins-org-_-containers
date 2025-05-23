FROM ubuntu:latest

USER root
RUN apt update && apt install -y sudo iproute2 iptables arptables ebtables git && \
    update-alternatives --set iptables /usr/sbin/iptables-legacy && \
    update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy && \
    update-alternatives --set arptables /usr/sbin/arptables-legacy && \
    update-alternatives --set ebtables /usr/sbin/ebtables-legacy && \
    useradd -m -s /bin/bash stack && \
    printf "stack\tALL=(ALL) NOPASSWD:ALL\n" >> /etc/sudoers

WORKDIR /home/stack
USER stack:stack
RUN git clone https://opendev.org/openstack/devstack && \
    cd devstack && \
    echo '[[local|localrc]]' > local.conf && \
    echo ADMIN_PASSWORD=password >> local.conf && \
    echo DATABASE_PASSWORD=password >> local.conf && \
    echo RABBIT_PASSWORD=password >> local.conf && \
    echo SERVICE_PASSWORD=password >> local.conf
    # sudo -u stack ./stack.sh

WORKDIR /home/stack/devstack
ENTRYPOINT ["/bin/bash"]
