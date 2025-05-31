FROM docker.io/library/alpine:3.22 as gcsfuse
ENV GOPATH=/go
ARG TARGETARCH
ARG VERSION

ENV PATH $GOPATH/bin:$PATH

RUN \
    apk add --no-cache go upx \
    && go install -ldflags="-s -w" github.com/googlecloudplatform/gcsfuse@master \
    && upx /go/bin/gcsfuse

FROM 1password/connect-api:latest

COPY --from=gcsfuse /go/bin/gcsfuse /gcsfuse

ENTRYPOINT ["/gcsfuse"]