"""Windows port of the PC window (ps2run.exe): a Windows window target for wgpu, Windows versions of the title-bar
CPU and memory readings, a big stack for the emulation thread, and a Windows branch in CMakeLists.txt.
Needs clang (clang-cl), SDL2 (the "devel VC" package) and the wgpu-native Windows release; see docs/windows-native-plan.md.
Usage (in the ps2-web-recomp folder, Linux or Windows copy): python3 ps2run_windows_patch.py [folder]
Safe to run twice. Changes five files: CMakeLists.txt, runtime/include/ps2/system.hpp, runtime/src/gs/gpu/gpu.hpp,
runtime/src/gs/gpu/gpu.cpp, host/window.cpp. The Linux and macOS builds behave as before.
"""
import os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

# (old text, new text) pairs per file; each old text occurs exactly once in the expected source
EDITS = {
    'CMakeLists.txt': [
        ('\nset(PS2_GENERATED "" CACHE PATH "Folder with the C++ generated for a game")\n\nif(EMSCRIPTEN)\n',
         '\nset(PS2_GENERATED "" CACHE PATH "Folder with the C++ generated for a game")\n\n# clang-cl treats -Wall as /Wall (every warning), so only add these for GNU-style drivers\nif(MSVC)\n    set(PS2_WARN "")\nelse()\n    set(PS2_WARN -Wall -Wextra)\nendif()\n\nif(EMSCRIPTEN)\n'),
        ('        recomp/codegen.cpp\n        recomp/snr2.cpp)\n    target_compile_options(eerecomp PRIVATE -Wall -Wextra)\n\n    add_executable(vujit_dump recomp/vujit_dump.cpp runtime/src/vu_jit.cpp)\n    target_include_directories(vujit_dump PRIVATE runtime/include runtime/src)\n    add_executable(vurecomp recomp/vurecomp.cpp)\n    target_include_directories(vurecomp PRIVATE runtime/include)\n    target_compile_options(vurecomp PRIVATE -Wall -Wextra)\nendif()\n\n',
         '        recomp/codegen.cpp\n        recomp/snr2.cpp)\n    target_compile_options(eerecomp PRIVATE ${PS2_WARN})\n\n    add_executable(vujit_dump recomp/vujit_dump.cpp runtime/src/vu_jit.cpp)\n    target_include_directories(vujit_dump PRIVATE runtime/include runtime/src)\n    add_executable(vurecomp recomp/vurecomp.cpp)\n    target_include_directories(vurecomp PRIVATE runtime/include)\n    target_compile_options(vurecomp PRIVATE ${PS2_WARN})\nendif()\n\n'),
        ('    runtime/src/iop/cdvdfsv.cpp)\ntarget_include_directories(ps2runtime PUBLIC runtime/include)\ntarget_compile_options(ps2runtime PRIVATE -Wall -Wextra)\n\nset(PS2_WGPU_DIR "${CMAKE_SOURCE_DIR}/third_party/wgpu-native" CACHE PATH "wgpu-native release folder")\nif(EMSCRIPTEN OR EXISTS "${PS2_WGPU_DIR}/lib/libwgpu_native.a")\n    set(PS2_GS_WGSL "${CMAKE_BINARY_DIR}/gs_wgsl.cpp")\n    add_custom_command(OUTPUT "${PS2_GS_WGSL}"\n',
         '    runtime/src/iop/cdvdfsv.cpp)\ntarget_include_directories(ps2runtime PUBLIC runtime/include)\ntarget_compile_options(ps2runtime PRIVATE ${PS2_WARN})\n\nset(PS2_WGPU_DIR "${CMAKE_SOURCE_DIR}/third_party/wgpu-native" CACHE PATH "wgpu-native release folder")\nif(EMSCRIPTEN OR EXISTS "${PS2_WGPU_DIR}/lib/libwgpu_native.a" OR EXISTS "${PS2_WGPU_DIR}/lib/wgpu_native.dll.lib")\n    set(PS2_GS_WGSL "${CMAKE_BINARY_DIR}/gs_wgsl.cpp")\n    add_custom_command(OUTPUT "${PS2_GS_WGSL}"\n'),
        ('    else()\n        target_include_directories(ps2runtime PRIVATE "${PS2_WGPU_DIR}/include")\n        target_link_libraries(ps2runtime PUBLIC "${PS2_WGPU_DIR}/lib/libwgpu_native.a" dl pthread m)\n        if(APPLE)\n            target_link_libraries(ps2runtime PUBLIC "-framework Metal" "-framework QuartzCore" "-framework Foundation" "-framework CoreFoundation" "-framework IOKit" "-framework IOSurface" objc)\n',
         '    else()\n        target_include_directories(ps2runtime PRIVATE "${PS2_WGPU_DIR}/include")\n        if(WIN32)\n            # Link the DLL\'s import library; wgpu_native.dll is copied next to ps2run.exe below.\n            target_link_libraries(ps2runtime PUBLIC "${PS2_WGPU_DIR}/lib/wgpu_native.dll.lib")\n        else()\n            target_link_libraries(ps2runtime PUBLIC "${PS2_WGPU_DIR}/lib/libwgpu_native.a" dl pthread m)\n        endif()\n        if(APPLE)\n            target_link_libraries(ps2runtime PUBLIC "-framework Metal" "-framework QuartzCore" "-framework Foundation" "-framework CoreFoundation" "-framework IOKit" "-framework IOSurface" objc)\n'),
        ('        target_compile_definitions(ps2run PRIVATE PS2_PROFILE)\n    endif()\n    find_package(SDL2 QUIET)\n    if(SDL2_FOUND AND NOT EMSCRIPTEN)\n        target_sources(ps2run PRIVATE host/window.cpp)\n        target_compile_definitions(ps2run PRIVATE PS2_WINDOW)\n        target_link_libraries(ps2run PRIVATE SDL2::SDL2)\n    endif()\nendif()\n',
         '        target_compile_definitions(ps2run PRIVATE PS2_PROFILE)\n    endif()\n    if(WIN32)\n        # SDL2 "devel VC" package: pass -DSDL2_DIR=<folder with include and lib>\n        set(SDL2_DIR "" CACHE PATH "Windows SDL2 development folder (contains include and lib)")\n        if(SDL2_DIR AND EXISTS "${SDL2_DIR}/include/SDL.h")\n            target_sources(ps2run PRIVATE host/window.cpp)\n            target_compile_definitions(ps2run PRIVATE PS2_WINDOW)\n            target_include_directories(ps2run PRIVATE "${SDL2_DIR}/include" "${SDL2_DIR}/include/SDL2")\n            target_link_libraries(ps2run PRIVATE "${SDL2_DIR}/lib/x64/SDL2.lib" psapi)\n            add_custom_command(TARGET ps2run POST_BUILD\n                COMMAND ${CMAKE_COMMAND} -E copy_if_different "${SDL2_DIR}/lib/x64/SDL2.dll" "$<TARGET_FILE_DIR:ps2run>"\n                COMMAND ${CMAKE_COMMAND} -E copy_if_different "${PS2_WGPU_DIR}/lib/wgpu_native.dll" "$<TARGET_FILE_DIR:ps2run>")\n        endif()\n    else()\n        find_package(SDL2 QUIET)\n        if(SDL2_FOUND AND NOT EMSCRIPTEN)\n            target_sources(ps2run PRIVATE host/window.cpp)\n            target_compile_definitions(ps2run PRIVATE PS2_WINDOW)\n            target_link_libraries(ps2run PRIVATE SDL2::SDL2)\n        endif()\n    endif()\nendif()\n'),
    ],
    'runtime/include/ps2/system.hpp': [
        ('\nstruct WindowTarget {\n    enum Kind { X11, Wayland, Canvas } kind = X11;\n    void *display = nullptr;\n    std::uint64_t window = 0;\n',
         '\nstruct WindowTarget {\n    enum Kind { X11, Wayland, Canvas, Win32 } kind = X11;\n    void *display = nullptr;\n    std::uint64_t window = 0;\n'),
    ],
    'runtime/src/gs/gpu/gpu.hpp': [
        ('\nstruct SurfaceTarget {\n    enum Kind { X11, Wayland, Canvas } kind;\n    void *display;\n    std::uint64_t window;\n',
         '\nstruct SurfaceTarget {\n    enum Kind { X11, Wayland, Canvas, Win32 } kind;\n    void *display;\n    std::uint64_t window;\n'),
    ],
    'runtime/src/gs/gpu/gpu.cpp': [
        ('    WGPUSurfaceSourceXlibWindow xlib = WGPU_SURFACE_SOURCE_XLIB_WINDOW_INIT;\n    WGPUSurfaceSourceWaylandSurface wayland = WGPU_SURFACE_SOURCE_WAYLAND_SURFACE_INIT;\n    if (target.kind == SurfaceTarget::X11) {\n        xlib.display = target.display;\n        xlib.window = target.window;\n        sd.nextInChain = &xlib.chain;\n    } else if (target.kind == SurfaceTarget::Wayland) {\n        wayland.display = target.display;\n        wayland.surface = target.surface;\n        sd.nextInChain = &wayland.chain;\n    } else {\n        return false;\n',
         '    WGPUSurfaceSourceXlibWindow xlib = WGPU_SURFACE_SOURCE_XLIB_WINDOW_INIT;\n    WGPUSurfaceSourceWaylandSurface wayland = WGPU_SURFACE_SOURCE_WAYLAND_SURFACE_INIT;\n    WGPUSurfaceSourceWindowsHWND win32 = WGPU_SURFACE_SOURCE_WINDOWS_HWND_INIT;\n    if (target.kind == SurfaceTarget::X11) {\n        xlib.display = target.display;\n        xlib.window = target.window;\n        sd.nextInChain = &xlib.chain;\n    } else if (target.kind == SurfaceTarget::Wayland) {\n        wayland.display = target.display;\n        wayland.surface = target.surface;\n        sd.nextInChain = &wayland.chain;\n    } else if (target.kind == SurfaceTarget::Win32) {\n        // display carries the HINSTANCE, window carries the HWND (set by host/window.cpp)\n        win32.hinstance = target.display;\n        win32.hwnd = reinterpret_cast<void *>(static_cast<std::uintptr_t>(target.window));\n        sd.nextInChain = &win32.chain;\n    } else {\n        return false;\n'),
    ],
    'host/window.cpp': [
        ('#include <SDL.h>\n#include <SDL_syswm.h>\n#include <sys/resource.h>\n#include <unistd.h>\n\n#include <algorithm>\n#include <atomic>\n#include <cmath>\n#include <cstdio>\n#include <cctype>\n#include <cstdlib>\n#include <cstring>\n#include <thread>\n#include <deque>\n',
         '#include <SDL.h>\n#include <SDL_syswm.h>\n#ifdef _WIN32\n#define NOMINMAX\n#define WIN32_LEAN_AND_MEAN\n#include <windows.h>\n#include <psapi.h>\n#else\n#include <sys/resource.h>\n#include <unistd.h>\n#endif\n\n#include <algorithm>\n#include <atomic>\n#include <cmath>\n#include <cstdio>\n#include <cctype>\n#include <cstdlib>\n#include <cstring>\n#include <functional>\n#include <thread>\n#include <deque>\n'),
        ('        target.display = info.info.x11.display;\n        target.window = static_cast<std::uint64_t>(info.info.x11.window);\n        break;\n#endif\n',
         '        target.display = info.info.x11.display;\n        target.window = static_cast<std::uint64_t>(info.info.x11.window);\n        break;\n#endif\n#if defined(SDL_VIDEO_DRIVER_WINDOWS)\n    case SDL_SYSWM_WINDOWS:\n        target.kind = ps2::WindowTarget::Win32;\n        target.display = info.info.win.hinstance;\n        target.window = static_cast<std::uint64_t>(reinterpret_cast<std::uintptr_t>(info.info.win.window));\n        break;\n#endif\n'),
        ('}\n\ndouble process_cpu_seconds() {\n    rusage usage{};\n',
         '}\n\n#ifdef _WIN32\ndouble process_cpu_seconds() {\n    FILETIME created, exited, kernel, user;\n    if (!GetProcessTimes(GetCurrentProcess(), &created, &exited, &kernel, &user)) return 0.0;\n    const auto ticks = [](const FILETIME &f) { return static_cast<double>((static_cast<std::uint64_t>(f.dwHighDateTime) << 32) | f.dwLowDateTime); };\n    return (ticks(kernel) + ticks(user)) / 1.0e7;\n}\n\ndouble resident_mb() {\n    PROCESS_MEMORY_COUNTERS pmc{};\n    if (!GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof pmc)) return 0.0;\n    return static_cast<double>(pmc.WorkingSetSize) / (1024.0 * 1024.0);\n}\n#else\ndouble process_cpu_seconds() {\n    rusage usage{};\n'),
        ('    return static_cast<double>(resident) * static_cast<double>(sysconf(_SC_PAGESIZE)) / (1024.0 * 1024.0);\n}\n\nvoid show_speed() {\n',
         '    return static_cast<double>(resident) * static_cast<double>(sysconf(_SC_PAGESIZE)) / (1024.0 * 1024.0);\n}\n#endif\n\nvoid show_speed() {\n'),
        ('}\n\nint run_window(const std::function<int()> &emulate) {\n    ps2::init_graphics();\n',
         '}\n\n// The emulation thread needs a deep stack (the browser build asks for 16 MB; Linux threads get 8 MB,\n// Windows threads only 1 MB by default).\nclass EmulationThread {\npublic:\n    void start(std::function<void()> body) {\n        body_ = std::move(body);\n#ifdef _WIN32\n        handle_ = CreateThread(nullptr, 64u << 20, &EmulationThread::entry, this, STACK_SIZE_PARAM_IS_A_RESERVATION, nullptr);\n        if (!handle_) body_();\n#else\n        thread_ = std::thread(body_);\n#endif\n    }\n    void join() {\n#ifdef _WIN32\n        if (handle_) {\n            WaitForSingleObject(handle_, INFINITE);\n            CloseHandle(handle_);\n            handle_ = nullptr;\n        }\n#else\n        thread_.join();\n#endif\n    }\n\nprivate:\n    std::function<void()> body_;\n#ifdef _WIN32\n    HANDLE handle_ = nullptr;\n    static DWORD WINAPI entry(LPVOID self) {\n        static_cast<EmulationThread *>(self)->body_();\n        return 0;\n    }\n#else\n    std::thread thread_;\n#endif\n};\n\nint run_window(const std::function<int()> &emulate) {\n    ps2::init_graphics();\n'),
        ('    std::atomic<bool> done{false};\n    int result = 0;\n    std::thread emulation([&] {\n        result = emulate();\n        done.store(true);\n',
         '    std::atomic<bool> done{false};\n    int result = 0;\n    EmulationThread emulation;\n    emulation.start([&] {\n        result = emulate();\n        done.store(true);\n'),
    ],
}


def main():
    done = skipped = 0
    for rel, pairs in EDITS.items():
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            print("PATCH NOT APPLIED: %s not found (run in the ps2-web-recomp folder)" % rel)
            return 1
        text = open(path, newline="").read()
        crlf = "\r\n" in text
        work = text.replace("\r\n", "\n")
        if all(new in work for _, new in pairs):
            skipped += len(pairs)
            continue
        for old, new in pairs:
            if work.count(old) != 1:
                print("PATCH NOT APPLIED: %s does not look like the expected source" % rel)
                return 1
        for old, new in pairs:
            work = work.replace(old, new, 1)
            done += 1
        if crlf:
            work = work.replace("\n", "\r\n")
        if work != text:
            open(path, "w", newline="").write(work)
    print("already patched" if not done else "patched (%d edits, %d already there)" % (done, skipped))
    return 0


sys.exit(main())
