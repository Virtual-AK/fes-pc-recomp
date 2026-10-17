@echo off
rem Lists the machine code of four small functions of the game's file layer, for reading on your computer.
rem Run it from the folder that holds the p3fes_*.py tools (C:\p3fes). It writes fileasm.txt.
rem This is the game's own code: send it to me in this chat if I ask, but never upload it to GitHub.
set EXE=extracted3\SLUS_216.21
echo ==== 0x100D80 (the function that logs "REQ CDVD", 218 callers)> fileasm.txt
py p3fes_bf.py code %EXE% 0x100D80 -n 90 >> fileasm.txt
echo ==== 0x556048 (cvFsOpen)>> fileasm.txt
py p3fes_bf.py code %EXE% 0x556048 -n 110 >> fileasm.txt
echo ==== 0x5564E0 (cvFsReqRd)>> fileasm.txt
py p3fes_bf.py code %EXE% 0x5564E0 -n 30 >> fileasm.txt
echo ==== 0x555B10 (cvFsAddDev)>> fileasm.txt
py p3fes_bf.py code %EXE% 0x555B10 -n 40 >> fileasm.txt
echo Done. Send me fileasm.txt.
