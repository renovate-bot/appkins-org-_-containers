FROM quay.io/metal3-io/ironic:latest

RUN dnf -y install ipxe-bootimgs-aarch64 ipxe-bootimgs-x86 && \
    cp /usr/share/ipxe/arm64-efi/snponly.efi /tftpboot/snp-arm64.efi && \
    cp /usr/share/ipxe/ipxe-snponly-x86_64.efi /tftpboot/snp-x86_64.efi && \
    cp /usr/share/ipxe/ipxe-x86_64.efi /tftpboot/ipxe-x86_64.efi && \
    cp /usr/share/ipxe/undionly.kpxe /tftpboot/undionly.kpxe && \
    cp /usr/share/ipxe/ipxe-snponly-x86_64.efi /tftpboot/snp.efi && \
    dnf clean all
