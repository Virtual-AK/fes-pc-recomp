"""Windows setup for friends: the Ubuntu half copies source and generated code correctly, the batch files are well formed."""
import os, subprocess, sys, tempfile, shutil

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
sh = os.path.join(T, "p3fes_win_prepare.sh")
assert subprocess.run(["bash", "-n", sh]).returncode == 0

tmp = tempfile.mkdtemp()
try:
    d, w = os.path.join(tmp, "ps2"), os.path.join(tmp, "win")
    def put(p, txt="x"):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(txt)
    put(d + "/CMakeLists.txt", "cmake")
    put(d + "/runtime/a.cpp", "a")
    put(d + "/build/junk.o"); put(d + "/games/p3fes/disc/SLUS_216.21", "boot"); put(d + "/.git/config")
    put(d + "/tools/emsdk/big"); put(d + "/third_party/wgpu-native/lib/libwgpu_native.a"); put(d + "/third_party/other/keep.h")
    put(d + "/generated/p3fes/g1.cpp", "g1"); put(d + "/generated/p3fes/vu1_0.cpp", "new-vu")
    stub = os.path.join(tmp, "stub.py")
    put(stub, "import sys\nopen(sys.argv[1] + '/patched.txt', 'w').write('1')\nprint('patched (stub)')\n")
    env = dict(os.environ, P3F_DIR=d, P3F_WIN=w, P3F_WINPATCH=stub)

    def run():
        return subprocess.run(["bash", sh], env=env, capture_output=True, text=True)

    r = run()
    assert r.returncode == 1 and "p3fes_install.sh" in r.stdout, "must refuse before the Ubuntu install finished"
    put(d + "/.tools-ok", "")
    r = run()
    assert r.returncode == 0, r.stdout + r.stderr
    S = w + "/ps2-web-recomp"
    assert os.path.exists(S + "/runtime/a.cpp") and os.path.exists(S + "/patched.txt") and os.path.exists(S + "/third_party/other/keep.h")
    for bad in ("build", "games", ".git", "tools/emsdk", "third_party/wgpu-native", "generated"):
        assert not os.path.exists(os.path.join(S, bad)), bad + " must not be copied"
    assert open(w + "/generated/p3fes/g1.cpp").read() == "g1"
    assert open(w + "/SLUS_216.21").read() == "boot"
    # a compiled VU1 file already in the Windows folder is kept; a changed generated file is updated
    put(w + "/generated/p3fes/vu1_0.cpp", "compiled-from-recordings")
    put(d + "/generated/p3fes/g1.cpp", "g1-new")
    r = run()
    assert r.returncode == 0 and "1 files copied" in r.stdout, r.stdout
    assert open(w + "/generated/p3fes/vu1_0.cpp").read() == "compiled-from-recordings"
    assert open(w + "/generated/p3fes/g1.cpp").read() == "g1-new"
    # a patch that does not fit stops the setup
    put(stub, "print('PATCH NOT APPLIED: x')\n")
    r = run()
    assert r.returncode == 1 and "did not fit" in r.stdout
finally:
    shutil.rmtree(tmp, ignore_errors=True)

for name in ("p3fes_win_setup.bat", "p3fes_win_record.bat", "build_win.bat", "p3fes_win_mod.bat"):
    b = open(os.path.join(T, name), "rb").read()
    assert b.count(b"\r\n") == b.count(b"\n"), name + " needs Windows line endings (labels and goto break otherwise)"
setup = open(os.path.join(T, "p3fes_win_setup.bat")).read()
for need in ("SDL2-devel-2.32.2-VC.zip", "wgpu-windows-x86_64-msvc-release.zip", "v29.0.1.1", "Microsoft.VisualStudio.Component.VC.Llvm.Clang",
             "p3fes_win_prepare.sh", "vcvars64.bat", "build_win.bat game", "p3fes_vu_compile.sh", "ps2recomp_vubranch_patch.py"):
    assert need in setup, need
for gone in ("p3fes_win_record.bat", "p3fes_vu_compile.sh", "ps2recomp_vubranch_patch.py", "build_win.bat"):
    assert os.path.exists(os.path.join(T, gone)), gone
assert "PS2_WGPU_DIR" in open(os.path.join(T, "build_win.bat")).read()
assert "build-mod" in open(os.path.join(T, "build_win.bat")).read() and "build_win.bat\" game mod" in open(os.path.join(T, "p3fes_win_mod.bat")).read()
assert "PS2_VU_RECORD" in open(os.path.join(T, "p3fes_win_record.bat")).read()
print("ok Windows setup for friends: Ubuntu half copies source and generated code correctly, batch files well formed")
