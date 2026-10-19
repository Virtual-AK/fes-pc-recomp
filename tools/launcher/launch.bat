@echo off
rem Starts the Persona 3 FES launcher (needs the installer to have run once).
rem Keep this file next to p3fes_launcher.py. A small console window stays open while the launcher runs.
for /f "delims=" %%i in ('wsl.exe wslpath -a "%~dp0"') do set HERE=%%i
wsl.exe python3 "%HERE%p3fes_launcher.py"
