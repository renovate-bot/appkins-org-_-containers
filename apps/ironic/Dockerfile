FROM --platform=linux/arm64 ghcr.io/siderolabs/ipxe:v1.10.0-alpha.0-37-g359807b AS ipxe-linux-arm64
FROM --platform=linux/amd64 ghcr.io/siderolabs/ipxe:v1.10.0-alpha.0-37-g359807b AS ipxe-linux-amd64

FROM quay.io/metal3-io/ironic:latest

COPY --from=ipxe-linux-amd64 /usr/libexec/ipxe.efi /tftpboot/ipxe-amd64.efi
COPY --from=ipxe-linux-amd64 /usr/libexec/snp.efi /tftpboot/snp-amd64.efi
COPY --from=ipxe-linux-arm64 /usr/libexec/ipxe.efi /tftpboot/ipxe-arm64.efi
COPY --from=ipxe-linux-arm64 /usr/libexec/snp.efi /tftpboot/snp-arm64.efi
