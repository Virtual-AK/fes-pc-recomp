@echo off
rem Build the Windows PC window. Run from "x64 Native Tools Command Prompt for VS 2022".
rem   build_win.bat runtime   -> only the runtime library (quick check, no game code)
rem   build_win.bat game      -> the full ps2run.exe (compiles the generated game code; slow)
rem   build_win.bat game mod  -> the Direct Commands build, into build-mod (made by p3fes_win_mod.bat)
set ROOT=C:\p3fes\winbuild
set SRC=%ROOT%\ps2-web-recomp
set GEN=%ROOT%\generated\p3fes
set SDL=%ROOT%\SDL2-devel-2.32.2-VC\SDL2-2.32.2
set OUT=%ROOT%\build
if /i "%2"=="mod" (
  set GEN=%ROOT%\generated\p3fesmod
  set OUT=%ROOT%\build-mod
)
set WGPU=
if exist "%ROOT%\wgpu-native\lib\wgpu_native.dll.lib" set WGPU="-DPS2_WGPU_DIR=%ROOT%\wgpu-native"
set WHAT=%1
if "%WHAT%"=="" set WHAT=runtime
if "%WHAT%"=="game" (set TARGET=ps2run) else (set TARGET=ps2runtime)
cmake -S "%SRC%" -B "%OUT%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl "-DPS2_GENERATED=%GEN%" "-DSDL2_DIR=%SDL%" %WGPU% > "%ROOT%\configure.log" 2>&1
if errorlevel 1 (echo CONFIGURE FAILED, last lines of %ROOT%\configure.log: & powershell -command "Get-Content '%ROOT%\configure.log' -Tail 30" & exit /b 1)
echo Configured. Building %TARGET% ...
cmake --build "%OUT%" --target %TARGET% > "%ROOT%\build.log" 2>&1
if errorlevel 1 (echo BUILD FAILED, last lines of %ROOT%\build.log: & powershell -command "Get-Content '%ROOT%\build.log' -Tail 40" & exit /b 1)
echo BUILD OK
