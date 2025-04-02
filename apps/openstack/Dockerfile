# syntax=docker/dockerfile:1

FROM docker.io/python:3.10-alpine as dev

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache \
    build-base \
    libtool \
    autoconf \
    automake \
    gcc \
    musl-dev \
    python3-dev \
    linux-headers \
    postgresql-dev \
    libffi-dev \
    openssl-dev \
    git \
    expat-dev \
    apr-dev \
    apr-util-dev \
    pcre-dev \
    zlib-dev

# Create and activate virtual environment
RUN python -m venv venv
ENV PATH="/app/venv/bin":$PATH

# Install OpenStack components
# COPY requirements.txt requirements.txt
# RUN pip install -r requirements.txt

# Install OpenStack services and extract sample config files
RUN pip install \
    python-keystoneclient \
    python-glanceclient \
    python-cinderclient \
    python-neutronclient \
    python-ironicclient \
    python-novaclient \
    horizon \
    keystone \
    glance \
    cinder \
    neutron \
    ironic \
    nova \
    sqlalchemy \
    psycopg2-binary \
    pymysql \
    python-memcached \
    oslo.config \
    oslo.messaging \
    oslo.db \
    oslo.middleware \
    oslo.policy \
    mod-wsgi-httpd

# Create config directory
RUN mkdir -p /app/config

# Extract sample configuration files from the installed packages
RUN pip show keystone | grep Location | awk '{print $2}' | xargs -I{} find {} -name "keystone.conf.sample" -exec cp {} /app/config/keystone.conf \; && \
    pip show glance | grep Location | awk '{print $2}' | xargs -I{} find {} -name "glance-api.conf.sample" -exec cp {} /app/config/glance-api.conf \; && \
    pip show cinder | grep Location | awk '{print $2}' | xargs -I{} find {} -name "cinder.conf.sample" -exec cp {} /app/config/cinder.conf \; && \
    pip show neutron | grep Location | awk '{print $2}' | xargs -I{} find {} -name "neutron.conf.sample" -exec cp {} /app/config/neutron.conf \; && \
    pip show ironic | grep Location | awk '{print $2}' | xargs -I{} find {} -name "ironic.conf.sample" -exec cp {} /app/config/ironic.conf \; && \
    pip show nova | grep Location | awk '{print $2}' | xargs -I{} find {} -name "nova.conf.sample" -exec cp {} /app/config/nova.conf \;

FROM docker.io/python:3.10-alpine

WORKDIR /app

# Copy virtual environment from dev stage
COPY --from=dev /app/venv /app/venv
ENV PATH="/app/venv/bin":$PATH

# Copy configuration files
COPY --from=dev /app/config/ /app/config/

# Copy entrypoint script
COPY entrypoint.py /app/entrypoint.py

# Default environment variables
ENV KEYSTONE_DB_HOST=localhost \
    KEYSTONE_DB_USER=keystone \
    KEYSTONE_DB_PASSWORD=keystone \
    KEYSTONE_ADMIN_PASSWORD=admin \
    GLANCE_DB_HOST=localhost \
    GLANCE_DB_USER=glance \
    GLANCE_DB_PASSWORD=glance \
    CINDER_DB_HOST=localhost \
    CINDER_DB_USER=cinder \
    CINDER_DB_PASSWORD=cinder \
    NEUTRON_DB_HOST=localhost \
    NEUTRON_DB_USER=neutron \
    NEUTRON_DB_PASSWORD=neutron \
    IRONIC_DB_HOST=localhost \
    IRONIC_DB_USER=ironic \
    IRONIC_DB_PASSWORD=ironic \
    NOVA_DB_HOST=localhost \
    NOVA_DB_USER=nova \
    NOVA_DB_PASSWORD=nova \
    HORIZON_SECRET_KEY=supersecret \
    OPENSTACK_DEFAULT_DB_TYPE=sqlite \
    ENABLE_APPLICATION_CREDENTIALS=true \
    SERVICE_PROJECT_NAME=service \
    SERVICE_PROJECT_DOMAIN=Default

# Volume for persistent data
VOLUME ["/var/lib/openstack"]

# Expose ports
EXPOSE 80 5000 9292 8774 8775 8776 9696 6385

ENTRYPOINT ["python", "/app/entrypoint.py"]
