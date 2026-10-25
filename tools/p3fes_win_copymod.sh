#!/bin/bash
# Copies the mods build's generated game code from Ubuntu into the Windows build folder.
# A file is copied only when its content differs (so the compile stays incremental), and files that no longer exist in
# Ubuntu are removed, so old and new game code never get mixed. The recorded graphics code (vu1_*) is left alone.
SRC="$HOME/ps2-web-recomp/generated/p3fesmod"
DST=/mnt/c/p3fes/winbuild/generated/p3fesmod
ls "$SRC"/*.cpp >/dev/null 2>&1 || { echo "STOPPED: no mods game code in ~/ps2-web-recomp/generated/p3fesmod. Press BUILD in the launcher under Mods and Essential Mods first."; exit 1; }
mkdir -p "$DST"
copied=0; removed=0
for f in "$SRC"/*; do
  b=$(basename "$f")
  if ! cmp -s "$f" "$DST/$b"; then cp -f "$f" "$DST/$b" && copied=$((copied+1)); fi
done
for f in "$DST"/*; do
  b=$(basename "$f")
  case "$b" in vu1_*) continue;; esac
  if [ ! -e "$SRC/$b" ]; then rm -f "$f" && removed=$((removed+1)); fi
done
echo "game code: $copied copied or changed, $removed old files removed"
