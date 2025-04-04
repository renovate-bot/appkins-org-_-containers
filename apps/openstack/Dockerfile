# syntax=docker/dockerfile:1

FROM docker.io/chainguard/python:latest-dev as dev

WORKDIR /app

# Install build dependencies
# RUN apk add --no-cache \
#     build-base \
#     libtool \
#     autoconf \
#     automake \
#     gcc \
#     musl-dev \
#     python3-dev \
#     linux-headers \
#     postgresql-dev \
#     libffi-dev \
#     openssl-dev \
#     git \
#     expat-dev \
#     apr-dev \
#     apr-util-dev \
#     pcre-dev \
#     zlib-dev

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
    python-memcached \
    oslo.config \
    oslo.messaging \
    oslo.db \
    oslo.middleware \
    oslo.policy \
    keystoneauth1 \
    cryptography \
    uvicorn \
    asgiref \
    starlette \
    fastapi \
    gunicorn

# Create config directory
RUN mkdir -p /app/config

# Extract sample configuration files from the installed packages
RUN pip show keystone | grep Location | awk '{print $2}' | xargs -I{} find {} -name "keystone.conf.sample" -exec cp {} /app/config/keystone.conf \; && \
    pip show glance | grep Location | awk '{print $2}' | xargs -I{} find {} -name "glance-api.conf.sample" -exec cp {} /app/config/glance-api.conf \; && \
    pip show cinder | grep Location | awk '{print $2}' | xargs -I{} find {} -name "cinder.conf.sample" -exec cp {} /app/config/cinder.conf \; && \
    pip show neutron | grep Location | awk '{print $2}' | xargs -I{} find {} -name "neutron.conf.sample" -exec cp {} /app/config/neutron.conf \; && \
    pip show ironic | grep Location | awk '{print $2}' | xargs -I{} find {} -name "ironic.conf.sample" -exec cp {} /app/config/ironic.conf \; && \
    pip show nova | grep Location | awk '{print $2}' | xargs -I{} find {} -name "nova.conf.sample" -exec cp {} /app/config/nova.conf \;

FROM docker.io/chainguard/python:latest

WORKDIR /app

# Copy virtual environment from dev stage
COPY --from=dev /app/venv /app/venv
ENV PATH="/app/venv/bin":$PATH

# Copy configuration files
COPY --from=dev /app/config/ /app/config/

# Copy entrypoint script and healthcheck script
COPY entrypoint.py healthcheck.py /app/

# Default environment variables
ENV KEYSTONE_DB_HOST=localhost \
    KEYSTONE_DB_USER=keystone \
    KEYSTONE_DB_PASSWORD=keystone \
    KEYSTONE_ADMIN_PASSWORD=admin \
    GLANCE_DB_HOST=localhost \
    GLANCE_DB_USER=glance \
    GLANCE_DB_PASSWORD=glance \
    GLANCE_APP_CRED_SECRET=glance-secret \
    CINDER_DB_HOST=localhost \
    CINDER_DB_USER=cinder \
    CINDER_DB_PASSWORD=cinder \
    CINDER_APP_CRED_SECRET=cinder-secret \
    NEUTRON_DB_HOST=localhost \
    NEUTRON_DB_USER=neutron \
    NEUTRON_DB_PASSWORD=neutron \
    NEUTRON_APP_CRED_SECRET=neutron-secret \
    IRONIC_DB_HOST=localhost \
    IRONIC_DB_USER=ironic \
    IRONIC_DB_PASSWORD=ironic \
    IRONIC_APP_CRED_SECRET=ironic-secret \
    NOVA_DB_HOST=localhost \
    NOVA_DB_USER=nova \
    NOVA_DB_PASSWORD=nova \
    NOVA_APP_CRED_SECRET=nova-secret \
    HORIZON_DB_HOST=localhost \
    HORIZON_APP_CRED_SECRET=horizon-secret \
    HORIZON_SECRET_KEY=supersecret \
    OPENSTACK_DEFAULT_DB_TYPE=sqlite \
    RABBITMQ_HOST=localhost \
    RABBITMQ_PORT=5672 \
    RABBITMQ_USER=guest \
    RABBITMQ_PASSWORD=guest \
    RABBITMQ_VHOST=/ \
    RABBITMQ_USE_SSL=false \
    RABBITMQ_SSL_CA_FILE="" \
    RABBITMQ_SSL_CERT_FILE="" \
    RABBITMQ_SSL_KEY_FILE=""

# Volume for persistent data
VOLUME ["/var/lib/openstack", "/etc/keystone", "/var/lib/glance", "/var/lib/cinder", "/var/lib/nova", "/var/lib/ironic", "/var/lib/neutron"]

# Expose ports
EXPOSE 80 5000 9292 8774 8775 8776 9696 6385

# Add healthcheck using the Python script
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 CMD python /app/healthcheck.py

ENTRYPOINT ["python", "/app/entrypoint.py"]
