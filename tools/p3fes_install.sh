#!/usr/bin/env bash
# One-command install for Persona 3 FES on PC and in the browser (Windows 10/11 with Ubuntu, or plain Linux).
#
#   bash p3fes_install.sh [path-to-your-disc.iso]
#
# What it does, asking nothing unless it must:
#   1. installs the Ubuntu packages it needs (asks for your Ubuntu password once)
#   2. downloads the open-source PS2 Web Recomp project into ~/ps2-web-recomp
#   3. applies every tool patch from this folder, in the right order
#   4. translates and builds the game from YOUR disc image (the long step, up to a couple of hours the first time)
#   5. writes ~/ps2-web-recomp/play.sh, which starts the game server; open http://localhost:8620/ in Chrome or Edge
# It is safe to run again: finished steps are skipped, and it carries on where it stopped.
# No game data is downloaded or included. Everything it makes stays on your computer.
#
# Options:  --patches-only   stop after step 3 (checks that every patch fits)
#           --dir PATH       install somewhere other than ~/ps2-web-recomp
#           --name NAME      game name (default p3fes)
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/ps2-web-recomp"
NAME=p3fes
ISO=""
PATCHES_ONLY=0
PIN=c628ae843209f6e4cef34ec04efb6267a1618882   # tested version of snuri00/ps2-web-recomp (16 Oct 2026)
while [ $# -gt 0 ]; do
  case "$1" in
    --patches-only) PATCHES_ONLY=1 ;;
    --dir) DIR="$2"; shift ;;
    --name) NAME="$2"; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    -*) echo "Unknown option $1"; exit 2 ;;
    *) ISO="$1" ;;
  esac
  shift
done

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 1. packages
say "[1/5] Ubuntu packages"
PKGS="xz-utils git cmake ninja-build clang python3 python3-pip p7zip-full libsdl2-dev curl unzip build-essential mesa-vulkan-drivers vulkan-tools"
missing=""
if [ "$PATCHES_ONLY" = 1 ]; then
  echo "skipped (patch check only)"
elif command -v dpkg >/dev/null 2>&1; then
  for p in $PKGS; do dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"; done
  if [ -n "$missing" ]; then
    echo "Installing:$missing"
    if [ "$(id -u)" = 0 ]; then SUDO=""; else SUDO="sudo"; fi
    $SUDO apt-get update || fail "apt update failed. Check your internet connection and try again."
    $SUDO apt-get install -y $missing || fail "installing packages failed. Send me the last 20 lines."
  else
    echo "already installed"
  fi
else
  echo "No apt here: make sure these are installed: $PKGS"
fi

# ---------------------------------------------------------------- 2. project
say "[2/5] PS2 Web Recomp"
if [ -d "$DIR/scripts" ]; then
  echo "already at $DIR"
else
  git clone https://github.com/snuri00/ps2-web-recomp.git "$DIR" || fail "download failed. Check your internet connection and try again."
  # the tool patches were written and tested against this exact version of the project
  git -C "$DIR" checkout -q "$PIN" || fail "could not select the tested project version ($PIN)."
  echo "using the tested version $PIN"
fi
cd "$DIR" || fail "cannot open $DIR"

# ---------------------------------------------------------------- 3. patches
say "[3/5] Tool patches"
# order matters: a patch listed later may need an earlier one (the movie-edge fix builds on the first picture-trace patches,
# which only add switches that stay off unless you set them)
PATCHES="
ps2run_trace_patch.py
ps2run_trace_patch2.py
ps2run_trace_patch3.py
ps2run_trace_patch4.py
ps2run_trace_patch5.py
ps2run_trace_patch6.py
ps2run_trace_patch9.py
ps2run_fix_path3_mask.py
ps2run_vubranch_patch.py
ps2recomp_vubranch_patch.py
ps2web_vubranch_patch.py
ps2run_vif_v2zero_patch.py
ps2gpu_tricenter_patch.py
ps2gpu_flipfix_patch.py
ps2gs_uploadclamp_patch.py
ps2run_controls_patch.py
ps2run_keyremap_patch.py
ps2run_sifquiet_patch.py
ps2run_window_capture_patch.py
ps2run_window_savestate_patch.py
ps2run_autosave_patch.py
ps2run_overlay_patch.py
ps2run_widescreen_patch.py
ps2run_widescreen_web_patch.py
ps2run_turbo_patch.py
ps2run_probe_patch.py
ps2run_disclog_patch.py
ps2run_dialoglog_patch.py
ps2run_mouselook_patch.py
ps2run_speedrun_patch.py
ps2run_audio_patch.py
ps2run_audio2_patch.py
ps2run_audiosrc_patch.py
ps2web_cardbackup_patch.py
ps2web_controls_patch.py
ps2web_keyremap_patch.py
ps2web_padremap_patch.py
ps2web_autosave_patch.py
ps2web_autosaveopts_patch.py
ps2web_cardsync_patch.py
ps2web_autosavesync_patch.py
ps2web_serveovl_patch.py
ps2web_speedrun_patch.py
ps2web_turbo_patch.py
ps2web_gamebeat_patch.py
"
# Patches are not all safe to run twice once later patches have changed their text, so remember which ones were applied.
# A project folder patched by an older installer (no list yet) is put back to the original source first.
APPLIED="$DIR/.p3fes_applied"
if [ "$PATCHES_ONLY" != 1 ] && [ ! -f "$APPLIED" ] && [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
  echo "Putting the project source back to the original before applying the patches (an earlier run changed it)"
  git checkout -q -- . || fail "could not restore the original project source."
fi
for f in $PATCHES; do
  if [ "$PATCHES_ONLY" != 1 ] && grep -qx "$f" "$APPLIED" 2>/dev/null; then
    echo "$f: applied earlier"
    continue
  fi
  [ -f "$HERE/$f" ] || fail "$f is missing from $HERE. Keep p3fes_install.sh inside the tools folder of the repository."
  out=$(python3 "$HERE/$f" 2>&1); rc=$?
  echo "$f: $(echo "$out" | tail -1)"
  if [ $rc -ne 0 ] || echo "$out" | grep -q "PATCH NOT APPLIED"; then
    echo "$out" | tail -5
    fail "$f did not fit the downloaded project (it may have changed). Send me this screen."
  fi
  [ "$PATCHES_ONLY" = 1 ] || echo "$f" >> "$APPLIED"
done
[ "$PATCHES_ONLY" = 1 ] || touch "$DIR/.tools-ok"   # the launcher reads this to show "get the tools: done"
if [ "$PATCHES_ONLY" = 1 ]; then echo; echo "All patches fit."; exit 0; fi

# ---------------------------------------------------------------- 4. disc
say "[4/5] Your disc image"
if [ -z "$ISO" ] && [ -e "games/$NAME/disc.iso" ]; then
  ISO="games/$NAME/disc.iso"
fi
if [ -z "$ISO" ]; then
  for c in /mnt/c/p3fes/*.iso "$HOME"/p3fes.iso "$HOME"/*.iso; do
    case "$c" in *[Mm]odded*) continue ;; esac
    if [ -f "$c" ]; then ISO="$c"; break; fi
  done
fi
[ -n "$ISO" ] && [ -e "$ISO" ] || fail "no disc image found. Put your own Persona 3 FES .iso in C:\\p3fes (or run: bash p3fes_install.sh /path/to/disc.iso)."
echo "using $ISO"
case "$ISO" in
  /mnt/*)
    # reading from the Windows disk is slow: copy once to Linux's own disk
    if [ ! -e "games/$NAME/disc.iso" ] && [ -e "$HOME/p3fes.iso" ] && [ "$(stat -c %s "$HOME/p3fes.iso")" != "$(stat -c %s "$ISO")" ]; then
      echo "the disc you chose differs from the copy in $HOME/p3fes.iso, replacing it"
      rm -f "$HOME/p3fes.iso"
    fi
    if [ ! -e "$HOME/p3fes.iso" ] && [ ! -e "games/$NAME/disc.iso" ]; then
      echo "copying to $HOME/p3fes.iso (about 4.5 GB, one time)"
      cp "$ISO" "$HOME/p3fes.iso" || fail "copy failed. Is there about 10 GB of free space?"
    fi
    if [ -e "$HOME/p3fes.iso" ]; then ISO="$HOME/p3fes.iso"; fi ;;
esac

# ---------------------------------------------------------------- 4b. a Node.js that works here
# The Emscripten download brings Node 24, which older Ubuntu-on-Windows (WSL1) cannot run ("Exec format error").
# If it does not work, use Node 20 instead (downloaded once from nodejs.org into ~/node20).
say "[5/5] Build tools (browser compiler)"
if [ ! -f tools/emsdk/emsdk_env.sh ]; then
  scripts/setup.sh || fail "setting up the browser compiler failed. Send me the last 30 lines."
fi
cfg="tools/emsdk/.emscripten"
if [ -f "$cfg" ]; then
  cur=$(sed -n "s/^NODE_JS = '\(.*\)'.*/\1/p" "$cfg" | sed "s#\\\$CFGDIR#$DIR/tools/emsdk#")
  if [ -n "$cur" ] && "$cur" --version >/dev/null 2>&1; then
    echo "Node works: $("$cur" --version)"
  else
    if ! "$HOME/node20/bin/node" --version >/dev/null 2>&1; then
      echo "The bundled Node does not run here. Downloading Node 20 (about 25 MB)"
      rm -rf "$HOME/node20"; mkdir -p "$HOME/node20"
      curl -fL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz | tar -xJ -C "$HOME/node20" --strip-components=1 \
        || fail "could not download Node 20. Check your internet connection and try again."
    fi
    "$HOME/node20/bin/node" --version >/dev/null 2>&1 || fail "Node 20 does not run here either. Send me this screen."
    sed -i "s#^NODE_JS = .*#NODE_JS = '$HOME/node20/bin/node'#" "$cfg"
    echo "Using Node $("$HOME/node20/bin/node" --version) from ~/node20"
  fi
fi

# ---------------------------------------------------------------- 5. build
say "Translating and building the game (this is the long step)"
echo "It can sit quietly for a long time. Leave this window open."
if [ -f "build/web-$NAME/ps2web.html" ]; then
  echo "already built: delete build/web-$NAME to rebuild"
  if ! grep -q -e "ps2-card-sync" -e "CS_URL" "build/web-$NAME/ps2web.html" 2>/dev/null || ! grep -q "asDiskSync" "build/web-$NAME/ps2web.html" 2>/dev/null || ! grep -q "ps2-gamebeat" "build/web-$NAME/ps2web.html" 2>/dev/null; then
    echo "Updating the browser page with the newest patches (a few minutes, no full rebuild)"
    scripts/build_web.sh "$NAME" || fail "updating the browser page failed. Send me the last 30 lines of this window."
  fi
else
  scripts/port.sh "$NAME" "$ISO" || fail "the build stopped. Send me the last 30 lines of this window."
fi
# the Direct Commands browser page (if you built it) is a separate build: bring it up to date too
if [ -f "build/web-p3fesmod/ps2web.html" ] && ! grep -q "ps2-gamebeat" "build/web-p3fesmod/ps2web.html" 2>/dev/null; then
  echo "Updating the Direct Commands browser page too (a few minutes)"
  scripts/build_web.sh p3fesmod || echo "Note: the Direct Commands page could not be updated; the normal game is fine."
fi
[ -f "build/web-$NAME/ps2web.html" ] || echo "Note: no browser build found in build/web-$NAME. If the lines above show an error, send me the last 30 lines."

cat > "$DIR/play.sh" <<EOF
#!/usr/bin/env bash
# Starts the game for the browser. Open http://localhost:8620/ in Chrome or Edge. Ctrl+C stops it.
cd "\$(dirname "\$0")" || exit 1
echo "Open http://localhost:8620/ in Chrome or Edge. Press Ctrl+C here to stop."
python3 scripts/serve.py build/web-$NAME games/$NAME/disc.iso
EOF
chmod +x "$DIR/play.sh"

say "Done"
echo "To play, in an Ubuntu window:"
echo "  $DIR/play.sh"
echo "then open http://localhost:8620/ in Chrome or Edge."
