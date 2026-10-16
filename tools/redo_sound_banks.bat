@echo off
rem Decodes the sound banks of extracted3 (the .SE files were already split by redo_exports.bat).
rem Run it from C:\p3fes. The wav files go into a "wav" folder inside each .SE.d folder in extracted3.
py p3fes_bed.py banks extracted3 -o redo3_bank_report.txt
(
echo sound bank wavs:
dir /s /b extracted3\*.wav ^| find /c ".SE.d"
) > redo3_bank_counts.txt
echo Done. Send me redo3_bank_report.txt and redo3_bank_counts.txt.
