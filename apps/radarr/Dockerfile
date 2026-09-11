# Stage 1: Builder
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder

# 1. Install Node.js, Yarn, Git, libmediainfo, and ca-certificates
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs git libmediainfo0v5 ca-certificates \
    && npm install -g yarn

# 2. Gather libmediainfo and ALL its dynamic dependencies
# We use ldd to find linked libraries, filter for absolute paths, and copy them (without overwriting core libs)
RUN mkdir -p /dist-deps/lib && \
    ldd /usr/lib/x86_64-linux-gnu/libmediainfo.so | grep "=> /" | awk '{print $3}' | xargs -I '{}' cp -n '{}' /dist-deps/lib/ && \
    cp /usr/lib/x86_64-linux-gnu/libmediainfo.so.* /dist-deps/lib/

WORKDIR /source

# 3. Clone repository
RUN git clone --depth 1 https://github.com/Radarr/Radarr.git .

# 4. Build Frontend
WORKDIR /source/frontend
RUN yarn install && yarn build

# 5. Build Backend (Single Compressed Binary)
WORKDIR /source
RUN dotnet publish src/Radarr.Console/Radarr.Console.csproj \
    -c Release \
    -r linux-x64 \
    --self-contained true \
    -p:PublishSingleFile=true \
    -p:IncludeNativeLibrariesForSelfExtract=true \
    -p:EnableCompressionInSingleFile=true \
    -o /app/out

# Stage 2: Distroless Runtime
FROM gcr.io/distroless/cc-debian12

WORKDIR /app

# Copy the dependencies and certificates gathered in the builder
# Distroless cc-debian12 includes glibc/libstdc++, so we dump our deps into /usr/lib
COPY --from=builder /dist-deps/lib/ /usr/lib/
COPY --from=builder /etc/ssl/certs/ /etc/ssl/certs/

# Copy the Radarr binary
COPY --from=builder /app/out/Radarr /app/Radarr

VOLUME ["/config"]
EXPOSE 7878

ENTRYPOINT ["/app/Radarr", "-nobrowser", "-data=/config"]
