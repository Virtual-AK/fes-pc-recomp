@echo off
rem Builds the Direct Commands version of the PC window (needed for the Direct Commands toggle in the launcher to work in the PC window).
rem Run it from "x64 Native Tools Command Prompt for VS 2022". It needs the normal PC window already built (p3fes_win_setup.bat) and the
rem Direct Commands build already made in Ubuntu (the browser version of the mod, scripts/port.sh p3fesmod).
rem It only copies the mod's generated game code; it does not touch the PC window's source or patches. Safe to run again.
rem The slow part is the compile (about as long as the normal PC window).
setlocal EnableExtensions
set ROOT=C:\p3fes\winbuild
echo == [1/3] Copying the Direct Commands game code from Ubuntu
wsl.exe bash -c "ls $HOME/ps2-web-recomp/generated/p3fesmod/*.cpp >/dev/null 2>&1 || { echo STOPPED: no Direct Commands game code in ~/ps2-web-recomp/generated/p3fesmod. Build the mod in Ubuntu first.; exit 1; }; mkdir -p /mnt/c/p3fes/winbuild/generated/p3fesmod && cp -u $HOME/ps2-web-recomp/generated/p3fesmod/* /mnt/c/p3fes/winbuild/generated/p3fesmod/"
if errorlevel 1 exit /b 1
echo == [2/3] Sharing the recorded graphics code with the normal build
if exist "%ROOT%\generated\p3fes\vu1_*" copy /Y "%ROOT%\generated\p3fes\vu1_*" "%ROOT%\generated\p3fesmod\" >nul
echo == [3/3] Building (slow)
call "%~dp0build_win.bat" game mod
if errorlevel 1 exit /b 1
echo.
echo Done. Press Play in the launcher with Direct Commands switched on (Mods, Direct Commands).
