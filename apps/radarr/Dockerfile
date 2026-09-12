# Stage 1: Builder
FROM mcr.microsoft.com/dotnet/sdk:11.0 AS builder

# Expose Docker's target architecture variable
ARG TARGETARCH

# 1. Install Node.js, Yarn, Git, libmediainfo, and ca-certificates
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs git libmediainfo0v5 ca-certificates \
    && npm install -g yarn

# 2. Gather libmediainfo and ALL its dynamic dependencies
RUN mkdir -p /dist-deps/lib && \
    LIB_PATH=$(find /usr/lib -name "libmediainfo.so*" | head -n 1) && \
    ldd $LIB_PATH | grep "=> /" | awk '{print $3}' | xargs -I '{}' cp -n '{}' /dist-deps/lib/ && \
    cp /usr/lib/*/libmediainfo.so.* /dist-deps/lib/

WORKDIR /source

# 3. Clone repository
RUN git clone --depth 1 https://github.com/Radarr/Radarr.git .

# 4. Build Frontend
WORKDIR /source/frontend
RUN yarn install && yarn build

# 5. Build Backend dynamically based on architecture
WORKDIR /source
RUN if [ "$TARGETARCH" = "amd64" ]; then RID="linux-x64"; \
    elif [ "$TARGETARCH" = "arm64" ]; then RID="linux-arm64"; \
    elif [ "$TARGETARCH" = "arm" ]; then RID="linux-arm"; \
    else RID="linux-x64"; fi \
    && dotnet publish src/Radarr.Host/Radarr.Host.csproj \
    -c Release \
    -r $RID \
    --self-contained true \
    -p:PublishSingleFile=true \
    -p:IncludeNativeLibrariesForSelfExtract=true \
    -p:EnableCompressionInSingleFile=true \
    -o /app/out

# Stage 2: Distroless Runtime
FROM gcr.io/distroless/cc-debian12

WORKDIR /app

COPY --from=builder /dist-deps/lib/ /usr/lib/
COPY --from=builder /etc/ssl/certs/ /etc/ssl/certs/
COPY --from=builder /app/out/Radarr /app/Radarr

VOLUME ["/config"]
EXPOSE 7878

ENTRYPOINT ["/app/Radarr", "-nobrowser", "-data=/config"]
