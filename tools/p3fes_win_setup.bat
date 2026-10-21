@echo off
rem One-step setup of the Persona 3 FES PC window (native Windows). Double-click it, or run it from a Command Prompt.
rem Needs first: Windows 10/11 with Ubuntu (WSL) and p3fes_install.sh finished once (see docs/install.md).
rem Keep this file inside the repository's tools folder. It is safe to run again: finished steps are skipped.
rem   1. installs Visual Studio Build Tools with clang + CMake (asks Windows for permission; about 3 GB, one time)
rem   2. downloads SDL2 and wgpu-native (open-source libraries, from their GitHub release pages)
rem   3. prepares C:\p3fes\winbuild from your Ubuntu install (p3fes_win_prepare.sh)
rem   4. builds ps2run.exe (about 5 to 10 minutes)
setlocal EnableExtensions
set ROOT=C:\p3fes\winbuild
set PF86=%ProgramFiles(x86)%
set VSW=%PF86%\Microsoft Visual Studio\Installer\vswhere.exe
set OPTS=--add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --add Microsoft.VisualStudio.Component.VC.CMake.Project --includeRecommended
if not exist "%ROOT%" mkdir "%ROOT%"

echo.
echo == [1/4] Build tools (Visual Studio Build Tools with clang and CMake)
set VSDIR=
if exist "%VSW%" for /f "usebackq delims=" %%i in (`"%VSW%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Llvm.Clang Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath`) do set VSDIR=%%i
if defined VSDIR goto have_tools
set ANYVS=
if exist "%VSW%" for /f "usebackq delims=" %%i in (`"%VSW%" -latest -products * -property installationPath`) do set ANYVS=%%i
if defined ANYVS goto modify_vs
echo Installing with winget. Windows will ask for permission; this takes a while.
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart %OPTS%"
goto tools_check
:modify_vs
echo Adding clang and CMake to the Visual Studio found in %ANYVS%
"%PF86%\Microsoft Visual Studio\Installer\setup.exe" modify --installPath "%ANYVS%" %OPTS% --quiet --wait --norestart
:tools_check
if exist "%VSW%" for /f "usebackq delims=" %%i in (`"%VSW%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Llvm.Clang Microsoft.VisualStudio.Component.VC.CMake.Project -property installationPath`) do set VSDIR=%%i
if defined VSDIR goto have_tools
echo.
echo STOPPED: the build tools are not installed. If Windows asked for permission and you said no, run this file again.
echo Otherwise install "Build Tools for Visual Studio 2022" by hand with the "Desktop development with C++" workload,
echo ticking "C++ Clang Compiler for Windows" and "C++ CMake tools", then run this file again.
goto fail
:have_tools
echo Found: %VSDIR%

echo.
echo == [2/4] SDL2 and wgpu-native
if exist "%ROOT%\SDL2-devel-2.32.2-VC\SDL2-2.32.2\include\SDL.h" goto have_sdl
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://github.com/libsdl-org/SDL/releases/download/release-2.32.2/SDL2-devel-2.32.2-VC.zip' -OutFile '%ROOT%\sdl2.zip'; Expand-Archive -Force '%ROOT%\sdl2.zip' '%ROOT%\SDL2-devel-2.32.2-VC'; Remove-Item '%ROOT%\sdl2.zip'"
if not exist "%ROOT%\SDL2-devel-2.32.2-VC\SDL2-2.32.2\include\SDL.h" echo STOPPED: SDL2 did not download. Check your internet connection and run this file again. & goto fail
:have_sdl
echo SDL2 ready
if exist "%ROOT%\wgpu-native\lib\wgpu_native.dll.lib" goto have_wgpu
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing 'https://github.com/gfx-rs/wgpu-native/releases/download/v29.0.1.1/wgpu-windows-x86_64-msvc-release.zip' -OutFile '%ROOT%\wgpu.zip'; Expand-Archive -Force '%ROOT%\wgpu.zip' '%ROOT%\wgpu-native'; Remove-Item '%ROOT%\wgpu.zip'"
if not exist "%ROOT%\wgpu-native\lib\wgpu_native.dll.lib" echo STOPPED: wgpu-native did not download. Check your internet connection and run this file again. & goto fail
:have_wgpu
echo wgpu-native ready

echo.
echo == [3/4] Preparing the build folder from your Ubuntu install
set HERE=
for /f "delims=" %%i in ('wsl.exe wslpath -a "%~dp0"') do set HERE=%%i
if not defined HERE echo STOPPED: Ubuntu (WSL) did not answer. Install it first, see docs/install.md. & goto fail
wsl.exe bash "%HERE%p3fes_win_prepare.sh"
if errorlevel 1 goto fail
copy /y "%~dp0build_win.bat" "%ROOT%\build_win.bat" >nul
copy /y "%~dp0p3fes_win_record.bat" "%ROOT%\p3fes_win_record.bat" >nul
copy /y "%~dp0p3fes_vu_compile.sh" "%ROOT%\p3fes_vu_compile.sh" >nul
copy /y "%~dp0ps2recomp_vubranch_patch.py" "%ROOT%\ps2recomp_vubranch_patch.py" >nul

echo.
echo == [4/4] Building ps2run.exe (the first build takes a while)
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 echo STOPPED: could not start the Visual Studio build environment. & goto fail
cd /d "%ROOT%"
call build_win.bat game
if errorlevel 1 goto fail

echo.
echo Done: %ROOT%\build\ps2run.exe
echo Open the launcher (launch.bat) and press Play: it starts this window when ps2run.exe exists.
echo.
echo For smooth play in every scene, record and compile the missing VU1 programs, see docs/windows-friends-setup.md.
echo In short: run %ROOT%\p3fes_win_record.bat and play through different scenes, then
echo   wsl bash /mnt/c/p3fes/winbuild/p3fes_vu_compile.sh
echo and build again in a Native Tools prompt: cd /d %ROOT% and build_win.bat game
pause
exit /b 0

:fail
echo.
pause
exit /b 1
