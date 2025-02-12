#!/bin/bash

sed -i 's/x86_64-linux-gnu/aarch64-linux-gnu/g' cmake/FindWebP.cmake
sed -i 's/x86_64-linux-gnu/aarch64-linux-gnu/g' cmake/FindFFmpeg.cmake

-DFFMPEG_ROOT=/usr/share/ffmpeg


-DFFMPEG_LIBAVFORMAT_INCLUDE_DIRS=/usr/include/aarch64-linux-gnu/libavformat -DFFMPEG_LIBAVDEVICE_INCLUDE_DIRS=/usr/include/aarch64-linux-gnu/libavdevice -DFFMPEG_LIBAVCODEC_INCLUDE_DIRS=/usr/include/aarch64-linux-gnu/libavcodec

rm -rf build-linux-aarch64
cmake -B build-linux-aarch64 -DAG_ENABLE_CODE_SIGNING=off -DCMAKE_BUILD_TYPE=RelWithDebInfo -DAG_WITH_PLUGIN=off -DAG_ENABLE_DEBUG_COPY_STEP=off -DFFMPEG_ROOT=/usr/include/aarch64-linux-gnu -DCMAKE_CXX_FLAGS="-Wno-type-limits -Wno-deprecated-declarations" -DAG_DEPS_ROOT=/audiogridder/audiogridder-deps/linux-aarch64
cmake --build build-linux-aarch64 -j6

VERSION=$(cat package/VERSION)

mkdir -p package/build/vst
mkdir -p package/build/vst3
mkdir -p package/build/tray

cp build-linux-aarch64/Plugin/AudioGridderFx_artefacts/RelWithDebInfo/VST/libAudioGridder.so package/build/vst/AudioGridder.so
cp build-linux-aarch64/Plugin/AudioGridderInst_artefacts/RelWithDebInfo/VST/libAudioGridderInst.so package/build/vst/AudioGridderInst.so
cp build-linux-aarch64/Plugin/AudioGridderMidi_artefacts/RelWithDebInfo/VST/libAudioGridderMidi.so package/build/vst/AudioGridderMidi.so
cp -r build-linux-aarch64/Plugin/AudioGridderFx_artefacts/RelWithDebInfo/VST3/AudioGridder.vst3 package/build/vst3/
cp -r build-linux-aarch64/Plugin/AudioGridderInst_artefacts/RelWithDebInfo/VST3/AudioGridderInst.vst3 package/build/vst3/
cp -r build-linux-aarch64/Plugin/AudioGridderMidi_artefacts/RelWithDebInfo/VST3/AudioGridderMidi.vst3 package/build/vst3/
cp build-linux-aarch64/PluginTray/AudioGridderPluginTray_artefacts/RelWithDebInfo/AudioGridderPluginTray package/build/tray/

cp package/build/vst/* ../Archive/Builds/$VERSION/linux
cp -r package/build/vst3/* ../Archive/Builds/$VERSION/linux
cp -r package/build/tray/* ../Archive/Builds/$VERSION/linux

cd package/build
zip -r AudioGridder_$VERSION-Linux.zip vst vst3 tray
zip -j AudioGridder_$VERSION-Linux.zip ../install-trayapp-linux.sh
rm -rf vst vst3 tray

mkdir -p build-linux-aarch64/bin
cp ./audiogridder-deps/linux-aarch64/bin/crashpad_handler ./build-linux-aarch64/bin/crashpad_handler
cmake -DCMAKE_BUILD_TYPE=


cmake --build build-linux-aarch64
