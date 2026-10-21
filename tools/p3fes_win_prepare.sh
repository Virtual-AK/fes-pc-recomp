#!/usr/bin/env bash
# Step 2 of the Windows PC window setup (called by p3fes_win_setup.bat, can also be run by hand).
# Takes the Ubuntu install made by p3fes_install.sh and prepares C:\p3fes\winbuild from it:
#   - copies the (already patched) project source, without build folders, game data or the Linux graphics library
#   - applies ps2run_windows_patch.py to that copy
#   - copies the C++ generated from YOUR disc, only the files that changed
#   - copies the boot file SLUS_216.21 from your install (the launcher also does this when you press Play)
# Nothing here is downloaded and nothing leaves your computer. Safe to run again.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="${P3F_DIR:-$HOME/ps2-web-recomp}"
WIN="${P3F_WIN:-/mnt/c/p3fes/winbuild}"
PATCH="${P3F_WINPATCH:-$HERE/ps2run_windows_patch.py}"
NAME="${P3F_NAME:-p3fes}"
fail() { echo "STOPPED: $*"; exit 1; }

[ -f "$DIR/CMakeLists.txt" ] || fail "no Ubuntu install found in $DIR. Run p3fes_install.sh first (see docs/install.md)."
[ -e "$DIR/.tools-ok" ] || fail "the Ubuntu install in $DIR did not finish its tool patches. Run p3fes_install.sh again."
GEN="$DIR/generated/$NAME"
ls "$GEN"/*.cpp >/dev/null 2>&1 || fail "no generated game code in $GEN. Let p3fes_install.sh finish the long build step first."
[ -f "$PATCH" ] || fail "$PATCH is missing. Keep this script inside the tools folder."

mkdir -p "$WIN/ps2-web-recomp" "$WIN/generated/$NAME" || fail "cannot create $WIN"

echo "[1/4] Copying the project source"
tar -C "$DIR" --exclude=./build --exclude=./games --exclude=./.git --exclude=./generated \
    --exclude=./tools/emsdk --exclude=./third_party/wgpu-native -cf - . | tar -C "$WIN/ps2-web-recomp" -xf - \
  || fail "copying the source to $WIN failed (is there free space on C:?)"

echo "[2/4] Applying the Windows patch"
out=$(python3 "$PATCH" "$WIN/ps2-web-recomp" 2>&1); rc=$?
echo "$out" | tail -3
if [ $rc -ne 0 ] || echo "$out" | grep -q "PATCH NOT APPLIED"; then
  fail "the Windows patch did not fit the copied source. Send me the lines above."
fi

echo "[3/4] Copying the generated game code"
new=0
for f in "$GEN"/*; do
  [ -f "$f" ] || continue
  b="$(basename "$f")"
  # vu1_* files are rebuilt from the recordings by p3fes_vu_compile.sh, so they are only seeded here when missing
  case "$b" in vu1_*) [ -e "$WIN/generated/$NAME/$b" ] && continue ;; esac
  if ! cmp -s "$f" "$WIN/generated/$NAME/$b"; then cp "$f" "$WIN/generated/$NAME/$b" && new=$((new + 1)); fi
done
echo "$new files copied or updated, $(ls "$WIN/generated/$NAME" | wc -l) in total"

echo "[4/4] Boot file"
SLUS="$DIR/games/$NAME/disc/SLUS_216.21"
if [ -f "$SLUS" ]; then cp -n "$SLUS" "$WIN/SLUS_216.21" && echo "SLUS_216.21 is in $WIN"; else echo "not found yet (the launcher copies it when you press Play)"; fi
echo "Prepared."
