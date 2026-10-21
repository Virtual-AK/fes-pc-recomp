@echo off
rem Starts the PC window in "recording" mode: every graphics program (VU1) the game uses that is not compiled yet is saved.
rem Play through many different scenes (school, town, Tartarus, battles, menus, cut-scenes), then close the window and run:
rem   wsl bash /mnt/c/p3fes/winbuild/p3fes_vu_compile.sh
rem   cd /d C:\p3fes\winbuild   and   build_win.bat game      (in the x64 Native Tools prompt)
rem Recorded files are pieces of the game's own code. They stay on your computer and must never be shared.
setlocal EnableExtensions
set ROOT=C:\p3fes\winbuild
set REC=%ROOT%\vu1rec
set ISO=
for %%f in ("C:\p3fes\*.iso") do call :pick "%%f"
if not defined ISO echo STOPPED: no disc image found in C:\p3fes. & pause & exit /b 1
if not exist "%ROOT%\build\ps2run.exe" echo STOPPED: build the PC window first with p3fes_win_setup.bat. & pause & exit /b 1
if not exist "%ROOT%\SLUS_216.21" echo STOPPED: SLUS_216.21 is missing from %ROOT%. Press Play in the launcher once, or run p3fes_win_prepare.sh. & pause & exit /b 1
if not exist "%REC%" mkdir "%REC%"
if not exist "C:\p3fes\saves" mkdir "C:\p3fes\saves"
set PS2_VU_RECORD=%REC%
echo Recording to %REC%. Close the game window when you are done.
"%ROOT%\build\ps2run.exe" "%ROOT%\SLUS_216.21" --disc "%ISO%" --window --memcard "C:\p3fes\saves\Mcd001.ps2"
echo.
dir /b "%REC%\*.bin" 2>nul | find /c /v "" 
echo recorded programs in total (see above). Next: wsl bash /mnt/c/p3fes/winbuild/p3fes_vu_compile.sh
pause
exit /b 0
:pick
echo %~nx1 | findstr /i "modded" >nul && exit /b 0
if not defined ISO set ISO=%~1
exit /b 0
