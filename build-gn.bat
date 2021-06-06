: Build GN in the project root
git clone https://gn.googlesource.com/gn gn
python gn\build\gen.py
ninja -C gn\out gn.exe
copy gn\out\gn.exe bin\