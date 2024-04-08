FROM alpine:latest

# Install Python3 and pip
RUN apk add --no-cache python3 py3-pip \
    py3-pexpect \
    py3-daemonize \
    py3-psutil \
    py3-setuptools \
    py3-flask \
    py3-flask-restful \
    py3-netaddr \
    py3-cryptography \
    py3-tz \
    py3-aniso8601 \
    uwsgi \
    uwsgi-python3 \
    py3-openssl && \
    apk add --no-cache curl openssh gcc bubblewrap unzip bzip2 libarchive-tools && \
    rm /usr/lib/python3.11/EXTERNALLY-MANAGED

RUN /usr/bin/python3 -m pip install --no-cache-dir ansible-runner==2.1.1

WORKDIR /root
RUN \
    mkdir -p /root/ansible-runner-service && \
    curl -sSL https://codeload.github.com/ansible/ansible-runner-service/zip/refs/heads/dependabot/pip/ansible-runner-2.1.1 | bsdtar xvf - --strip-components=1 -C /root/ansible-runner-service && \
    cd ansible-runner-service && \
    python3 setup.py install --record installed_files \
           --single-version-externally-managed

ENTRYPOINT ["/usr/bin/ansible_runner_service"]
