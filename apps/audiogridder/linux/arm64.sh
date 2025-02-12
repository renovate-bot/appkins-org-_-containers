#!/usr/bin/env sh

set -eu

apt update
apt install -y curl g++ libboost-all-dev cmake ca-certificates git libavcodec-dev libavdevice-dev libasound2-dev libjack-jackd2-dev ladspa-sdk libcurl4-openssl-dev libfreetype6-dev libx11-dev libxcomposite-dev libxcursor-dev libxext-dev libxinerama-dev libxrandr-dev libxrender-dev libwebkitgtk-6.0-4 libglu1-mesa-dev mesa-common-dev python3
git clone --recurse-submodules https://github.com/apohl79/audiogridder.git
cd audiogridder
sed -i 's/x86_64-linux-gnu/aarch64-linux-gnu/g' cmake/FindWebP.cmake
sed -i 's/x86_64-linux-gnu/aarch64-linux-gnu/g' cmake/FindFFmpeg.cmake
cmake -B build-linux-aarch64 -DAG_ENABLE_CODE_SIGNING=off -DCMAKE_BUILD_TYPE=RelWithDebInfo -DAG_WITH_PLUGIN=off -DAG_ENABLE_DEBUG_COPY_STEP=off
cmake --build build-linux-aarch64 -j6
