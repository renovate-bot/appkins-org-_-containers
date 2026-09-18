# syntax=docker/dockerfile:1

# Radarr release tag without the leading "v". build-images.yaml passes the value
# printed by ci/latest.sh.
ARG VERSION=6.4.4.10685
# Must match global.json in the Radarr tag above; upstream builds with exactly
# this SDK and treats warnings as errors.
ARG DOTNET_SDK_VERSION=8.0.421
ARG NODE_VERSION=20

# Every build stage is pinned to the build platform and cross compiles for
# TARGETARCH. build-images.yaml builds each platform in its own job and never
# sets up QEMU, so nothing built for the target architecture may run during the
# build: the .NET SDK cross publishes, the webpack output is architecture
# neutral, and the runtime libraries are unpacked from .deb files, not installed.

# ── Source ────────────────────────────────────────────────────────────────────
FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:${DOTNET_SDK_VERSION}-bookworm-slim AS source

ARG VERSION

ADD https://github.com/Radarr/Radarr/archive/refs/tags/v${VERSION}.tar.gz /radarr.tar.gz

WORKDIR /src

RUN tar -xzf /radarr.tar.gz --strip-components=1 -C /src \
    && rm /radarr.tar.gz

# Radarr ships here as one self-contained executable. Its assembly loader opens
# Radarr.*.dll by path at startup, so the bundle has to extract itself to
# DOTNET_BUNDLE_EXTRACT_BASE_DIR on first run, and AppContext.BaseDirectory then
# names that extraction directory instead of the executable's directory. Two
# lookups must keep pointing at the executable's own directory:
#   - ffprobe: the host extracts bundled files without the execute bit;
#   - package_info: the file Servarr apps read to learn they are packaged in a
#     container and must not update themselves.
# Each sed is guarded so the build fails loudly if upstream changes the lines.
RUN set -eux; \
    f=src/NzbDrone.Core/MediaFiles/MediaInfo/VideoFileInfoReader.cs; \
    grep -qF 'options.BinaryFolder = AppDomain.CurrentDomain.BaseDirectory' "$f"; \
    sed -i 's|options.BinaryFolder = AppDomain.CurrentDomain.BaseDirectory|options.BinaryFolder = Path.GetDirectoryName(Environment.ProcessPath) ?? AppDomain.CurrentDomain.BaseDirectory|' "$f"; \
    f=src/NzbDrone.Core/Configuration/DeploymentInfoProvider.cs; \
    grep -qF 'var bin = appFolderInfo.StartUpFolder;' "$f"; \
    sed -i 's|var bin = appFolderInfo.StartUpFolder;|var bin = Path.GetDirectoryName(Environment.ProcessPath) ?? appFolderInfo.StartUpFolder;|' "$f"

# ── Frontend: build.sh YarnInstall + RunWebpack ───────────────────────────────
FROM --platform=${BUILDPLATFORM} node:${NODE_VERSION}-bookworm-slim AS frontend

WORKDIR /src

COPY --from=source /src /src

RUN --mount=type=cache,id=radarr-yarn,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile --network-timeout 120000

# Writes _output/UI.
RUN yarn run build --env production

# ── Runtime libraries for the target architecture ─────────────────────────────
# distroless cc-debian12 already has glibc, libssl, libstdc++ and libgcc. .NET
# also needs ICU and zlib, and Radarr dlopens the system libsqlite3.so.0. Fetch
# the Debian packages for TARGETARCH through multiarch apt and unpack them, and
# record them in dpkg's status.d the way distroless does so scanners see them.
FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:${DOTNET_SDK_VERSION}-bookworm-slim AS runtime-libs

ARG TARGETARCH

RUN set -eux; \
    if [ "$(dpkg --print-architecture)" != "${TARGETARCH}" ]; then \
      dpkg --add-architecture "${TARGETARCH}"; \
    fi; \
    apt-get update; \
    mkdir -p /debs /rootfs/var/lib/dpkg/status.d; \
    cd /debs; \
    apt-get download "libicu72:${TARGETARCH}" "libsqlite3-0:${TARGETARCH}" "zlib1g:${TARGETARCH}"; \
    for deb in *.deb; do \
      dpkg-deb -x "${deb}" /rootfs; \
      dpkg-deb -f "${deb}" > "/rootfs/var/lib/dpkg/status.d/$(dpkg-deb -f "${deb}" Package)"; \
    done; \
    rm -rf /var/lib/apt/lists/*

# ── Backend: build.sh Build for a single RID, published as one file ───────────
FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:${DOTNET_SDK_VERSION}-bookworm-slim AS backend

ARG BUILDKIT_SBOM_SCAN_STAGE=true \
    TARGETARCH \
    VERSION

WORKDIR /src

COPY --from=source /src /src

# Extra MSBuild logic for the single-file publish, imported through
# CustomAfterMicrosoftCommonTargets so the upstream project files stay as-is.
COPY <<'EOF' /build/Radarr.Docker.targets
<Project>
  <ItemGroup Condition="'$(MSBuildProjectName)' == 'Radarr.Console'">
    <!-- Radarr.Host loads Radarr.Mono by file name at runtime rather than
         referencing it; upstream's solution-wide PublishAllRids target publishes
         both projects into one folder. Reference it so the bundle carries it. -->
    <ProjectReference Include="$(RadarrRootDir)src/NzbDrone.Mono/Radarr.Mono.csproj" />
    <!-- The webpack output, served from <startup folder>/UI. -->
    <Content Include="$(RadarrRootDir)_output/UI/**" Link="UI/%(RecursiveDir)%(Filename)%(Extension)" CopyToPublishDirectory="PreserveNewest" />
  </ItemGroup>

  <!-- Bundled files are extracted without the execute bit, so ffprobe stays a
       separate file next to the Radarr executable (see the source stage). -->
  <Target Name="RadarrDockerKeepFfprobeOutOfBundle" AfterTargets="ComputeResolvedFilesToPublishList" Condition="'$(MSBuildProjectName)' == 'Radarr.Console'">
    <ItemGroup>
      <ResolvedFileToPublish Condition="'%(ResolvedFileToPublish.RelativePath)' == 'ffprobe'">
        <ExcludeFromSingleFile>true</ExcludeFromSingleFile>
      </ResolvedFileToPublish>
    </ItemGroup>
  </Target>
</Project>
EOF

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) rid=linux-x64 ;; \
      arm64) rid=linux-arm64 ;; \
      *) echo "unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    echo "${rid}" > /rid

COPY --from=frontend /src/_output/UI /src/_output/UI

# build.sh's UpdateVersionNumber rewrites AssemblyVersion and
# AssemblyConfiguration in Directory.Build.props; passing them as global
# properties has the same effect. Radarr reports AssemblyConfiguration as its
# update branch, so it is "master" like the upstream stable release. build.sh's
# -p:Platform=Posix only picks the solution configuration that leaves the
# Windows-only projects out; publishing the console project directly needs no
# equivalent.
#
# Directory.Build.props finds stylecop.json through SolutionDir, which only a
# solution build sets; without it StyleCop falls back to defaults and fails the
# build (SA1200 on every using directive).
#
# Radarr expects <dir>/bin/<executable> with package_info in <dir>, the layout
# every Servarr container uses; the bin directory name is checked, not chosen.
RUN --mount=type=cache,id=radarr-nuget,target=/root/.nuget/packages \
    set -eux; \
    rid="$(cat /rid)"; \
    dotnet publish src/NzbDrone.Console/Radarr.Console.csproj \
      --configuration Release \
      --framework net8.0 \
      --runtime "${rid}" \
      --self-contained true \
      --output /publish \
      -p:SolutionDir=/src/src/ \
      -p:AssemblyVersion="${VERSION}" \
      -p:AssemblyConfiguration=master \
      -p:PublishSingleFile=true \
      -p:IncludeAllContentForSelfExtract=true \
      -p:EnableCompressionInSingleFile=true \
      -p:CustomAfterMicrosoftCommonTargets=/build/Radarr.Docker.targets; \
    install -D -m 0755 /publish/Radarr /out/app/bin/Radarr; \
    install -D -m 0755 /publish/ffprobe /out/app/bin/ffprobe; \
    printf 'PackageAuthor=[appkins](https://github.com/appkins-org/containers)\nPackageVersion=%s\nUpdateMethod=Docker\nBranch=master\n' "${VERSION}" \
      > /out/app/package_info

# ── Image ─────────────────────────────────────────────────────────────────────
# Only COPY below, which is what lets the image be assembled for either
# architecture from an amd64 builder.
FROM gcr.io/distroless/cc-debian12

ARG VERSION \
    BUILD_DATE

COPY --from=runtime-libs /rootfs/ /
COPY --from=backend /out/ /

# The executable extracts itself here on first start (a few hundred MB, gone
# with the container); /tmp is also Radarr's temp folder. Diagnostics are off so
# .NET creates no IPC sockets in /tmp.
ENV DOTNET_BUNDLE_EXTRACT_BASE_DIR=/tmp/.net \
    DOTNET_RUNNING_IN_CONTAINER=true \
    DOTNET_EnableDiagnostics=0

VOLUME ["/config"]
EXPOSE 7878
STOPSIGNAL SIGTERM
ENTRYPOINT ["/app/bin/Radarr", "-nobrowser", "-data=/config"]

LABEL org.opencontainers.image.authors="Appkins <github-radarr@appkins.io>"
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.description="Radarr movie collection manager, built from source as a single self-contained executable on distroless"
LABEL org.opencontainers.image.documentation="https://github.com/appkins-org/containers/tree/main/apps/radarr"
LABEL org.opencontainers.image.licenses="GPL-3.0-only"
LABEL org.opencontainers.image.source="https://github.com/Radarr/Radarr"
LABEL org.opencontainers.image.title="radarr"
LABEL org.opencontainers.image.url="https://github.com/appkins-org/containers"
LABEL org.opencontainers.image.vendor="Appkins <github-radarr@appkins.io>"
LABEL org.opencontainers.image.version=${VERSION}
