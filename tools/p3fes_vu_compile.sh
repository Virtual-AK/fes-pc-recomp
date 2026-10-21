#!/usr/bin/env bash
# Turns the VU1 programs recorded while playing the Windows PC window into compiled code for it.
# Run from Windows:  wsl bash /mnt/c/p3fes/winbuild/p3fes_vu_compile.sh
# Then rebuild:      build_win.bat game      (in the x64 Native Tools prompt, folder C:\p3fes\winbuild)
# Recording is done by starting the game with  set PS2_VU_RECORD=C:\p3fes\winbuild\vu1rec  and playing through different scenes.
set -u
DIR="${P3F_DIR:-$HOME/ps2-web-recomp}"
REC="${P3F_REC:-/mnt/c/p3fes/winbuild/vu1rec}"
OUT="${P3F_OUT:-/mnt/c/p3fes/winbuild/generated/p3fes}"
fail() { echo "STOPPED: $*"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
# the branch fix for the program compiler (cut-in portraits): apply it if the patch file sits next to this script
if [ -f "$HERE/ps2recomp_vubranch_patch.py" ]; then
  (cd "$DIR" && python3 "$HERE/ps2recomp_vubranch_patch.py" recomp/vurecomp.cpp) || fail "ps2recomp_vubranch_patch.py did not fit $DIR/recomp/vurecomp.cpp"
  ninja -C "$DIR/build/tools" vurecomp >/dev/null 2>&1 || fail "could not rebuild vurecomp in $DIR/build/tools"
fi
[ -x "$DIR/build/tools/vurecomp" ] || fail "vurecomp not found in $DIR/build/tools. Run the installer once so it is built."
[ -d "$REC" ] && ls "$REC"/*.bin >/dev/null 2>&1 || fail "no recorded programs in $REC. Start the game with PS2_VU_RECORD set first (see the comment at the top of this script)."
[ -d "$OUT" ] || fail "$OUT not found (the folder with the generated game code for the Windows build)."
mkdir -p "$DIR/games/p3fes/vu1" "$DIR/generated/p3fes"
before=$(ls "$DIR/games/p3fes/vu1"/*.bin 2>/dev/null | wc -l)
cp -n "$REC"/*.bin "$DIR/games/p3fes/vu1/"
after=$(ls "$DIR/games/p3fes/vu1"/*.bin | wc -l)
echo "recorded programs: $before before, $after now ($((after - before)) new)"
"$DIR/build/tools/vurecomp" "$DIR/games/p3fes/vu1" "$DIR/generated/p3fes" | tail -1 || fail "vurecomp failed"
rm -f "$OUT"/vu1_*.cpp
cp "$DIR/generated/p3fes"/vu1_*.cpp "$OUT"/ || fail "could not copy the compiled programs to $OUT"
echo "copied $(ls "$OUT"/vu1_*.cpp | wc -l) files to $OUT"
echo "Next: in the x64 Native Tools prompt run:  cd /d C:\\p3fes\\winbuild  and  build_win.bat game   (takes a few minutes)"
