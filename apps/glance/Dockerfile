FROM quay.io/airshipit/glance:2025.1-ubuntu_noble

RUN apt update -qq \
    && apt install -yq libpcre3 libpcre3-dev tini \
    && rm -rf /var/lib/apt/lists/*

RUN . "/var/lib/openstack/bin/activate" \
    && pip install --no-cache-dir redis pg8000 \
    && deactivate

COPY entrypoint.sh /entrypoint.sh

RUN cp /var/lib/openstack/etc/glance/glance-api-paste.ini /etc/glance/glance-api-paste.ini && \
    cp /var/lib/openstack/etc/glance/glance-api.conf /etc/glance/glance-api.conf && \
    cp /var/lib/openstack/etc/glance/glance-cache.conf /etc/glance/glance-cache.conf && \
    cp /var/lib/openstack/etc/glance/glance-manage.conf /etc/glance/glance-manage.conf && \
    cp /var/lib/openstack/etc/glance/glance-scrubber.conf /etc/glance/glance-scrubber.conf && \
    cp /var/lib/openstack/etc/glance/rootwrap.conf /etc/glance/rootwrap.conf && \
    cp -r /var/lib/openstack/etc/glance/metadefs /etc/glance/metadefs && \
    cp -r /var/lib/openstack/etc/glance/rootwrap.d /etc/glance/rootwrap.d && \
    install /var/lib/openstack/bin/uwsgi /usr/bin/uwsgi && \
    install /var/lib/openstack/bin/glance-wsgi-api /usr/bin/glance-wsgi-api && \
    chmod +x /entrypoint.sh

ENV UWSGI_HTTP_SOCKET=":9292" \
    UWSGI_ADD_HEADER="Connection: close" \
    UWSGI_BUFFER_SIZE="65535" \
    UWSGI_DIE_ON_TERM="true" \
    UWSGI_ENABLE_THREADS="true" \
    UWSGI_EXIT_ON_RELOAD="false" \
    UWSGI_HOOK_MASTER_START="unix_signal:15 gracefully_kill_them_all" \
    UWSGI_LAZY_APPS="true" \
    UWSGI_LOG_X_FORWARDED_FOR="true" \
    UWSGI_MASTER="true" \
    UWSGI_PROCNAME_PREFIX_SPACED="glance-api:" \
    UWSGI_ROUTE_USER_AGENT="^kube-probe.*donotlog:" \
    UWSGI_THUNDER_LOCK="true" \
    UWSGI_WORKER_RELOAD_MERCY="80" \
    UWSGI_WSGI_FILE="/usr/bin/glance-wsgi-api" \
    UWSGI_CONFIG="/etc/glance/glance-api-paste.ini" \
    GLANCE_CONF="/etc/glance/glance-api.conf"

ENTRYPOINT ["/entrypoint.sh"]
