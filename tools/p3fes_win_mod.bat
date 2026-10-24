@echo off
rem Builds the Packed-In Mods version of the PC window (needed for the mod switches in the launcher to work in the PC window).
rem Run it from "x64 Native Tools Command Prompt for VS 2022". It needs the normal PC window already built (p3fes_win_setup.bat) and the
rem mods build already made in Ubuntu (the launcher's BUILD button in Mods > Packed-In Mods, or tools/p3fes_packed_build.py).
rem It refreshes the PC window's copy of the source (so it has the mod switches) and copies the mods' generated game code. Safe to run again.
rem The slow part is the compile (about as long as the normal PC window).
setlocal EnableExtensions
set ROOT=C:\p3fes\winbuild
set HERE=
for /f "delims=" %%i in ('wsl.exe wslpath -a "%~dp0."') do set HERE=%%i
if not defined HERE echo STOPPED: Ubuntu (WSL) did not answer. & exit /b 1
echo == [0/3] Bringing the PC window source up to date (mod switches)
wsl.exe bash "%HERE%/p3fes_win_prepare.sh"
if errorlevel 1 exit /b 1
echo == [1/3] Copying the packed-in mods game code from Ubuntu
wsl.exe bash "%HERE%/p3fes_win_copymod.sh"
if errorlevel 1 exit /b 1
echo == [2/3] Sharing the recorded graphics code with the normal build
if exist "%ROOT%\generated\p3fes\vu1_*" copy /Y "%ROOT%\generated\p3fes\vu1_*" "%ROOT%\generated\p3fesmod\" >nul
echo == [3/3] Building (slow)
call "%~dp0build_win.bat" game mod
if errorlevel 1 exit /b 1
echo.
echo Done. Turn mods on in the launcher (Mods, Packed-In Mods) and press Play.
