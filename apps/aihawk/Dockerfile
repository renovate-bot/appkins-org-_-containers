FROM alpine:latest AS src
RUN apk add unzip wget curl libarchive-tools
RUN mkdir -p /opt/ ; \
  curl -sfL https://github.com/feder-cr/Auto_Jobs_Applier_AIHawk/archive/v3.zip | bsdtar xvzf - --strip-components=1 -C /opt

FROM docker.io/python:3.10-buster
ARG TARGETARCH
ARG VERSION

COPY --from=src /opt/ /app/

RUN python -m venv /app
ENV PATH="/app/bin:$PATH"

WORKDIR /app

RUN \
    apt update && apt install -y git chromium-driver \
    && pip install -Ur /app/requirements.txt

ENTRYPOINT ["python", "/app/main.py"]
