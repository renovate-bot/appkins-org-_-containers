FROM alpine:latest
COPY virt-fw-vars.py fw-vars.json /
RUN apk add py3-pip qemu-img py3-virtualenv && \
    pip install --break-system-packages virt-firmware==23.9 && \
    wget -qO- "https://github.com/pftf/RPi4/releases/download/v1.38/RPi4_UEFI_Firmware_v1.38.zip" | busybox unzip -d / - && \
    python3 virt-fw-vars.py -i RPI_EFI.fd -o RPI_EFI.fd --set-json /fw-vars.json
