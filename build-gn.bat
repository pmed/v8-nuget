: Build GN in the V8 source tree
pushd v8
git clone https://chromium.googlesource.com/chromium/src/tools/gn tools/gn
git clone https://chromium.googlesource.com/chromium/src/base base
cd tools\gn
bootstrap\bootstrap.py -s
echo Result in %cd%\out\Release
popd