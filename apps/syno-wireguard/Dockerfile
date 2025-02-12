FROM debian:latest AS src
RUN apt update && apt install -y curl kmod
RUN mkdir -p /opt/ ; \
  curl -sfL https://github.com/MrTpat/Auto_Jobs_Applier_AIHawk/archive/main.zip | bsdtar xvzf - --strip-components=1 -C /opt

FROM docker.io/python:3.11-slim-buster
ARG TARGETARCH
ARG VERSION

COPY --from=src /opt/ /app/

RUN python -m venv /app
ENV PATH="/app/bin:$PATH"

WORKDIR /app

RUN \
    apt update && apt install -y --no-install-recommends git chromium-driver && \
    rm -rf /var/lib/apt/lists/* && \
    rm -Rf /usr/share/doc && rm -Rf /usr/share/man && \
    apt clean && \
    pip install -Ur /app/requirements.txt

ENTRYPOINT ["python", "main.py"]
