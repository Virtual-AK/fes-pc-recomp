@echo off
rem Redoes the exports from extracted3 (made with the fixed unpacker).
rem Run it from the folder that holds the p3fes_*.py tools (C:\p3fes). It writes only NEW folders
rem (fields_out3, extracted3_text, extracted3_png, audio3); the sound banks are split next to their .SE files inside extracted3 (.SE.d folders, wavs in a wav subfolder) and a count file, redo3_counts.txt.
rem It takes a while (the pictures and the audio are the slow parts). Your game files are not changed.
echo [1/6] field models and textures
py p3fes_field.py fields extracted3\DATA.CVM\FIELD\PACK -o fields_out3
echo [2/6] text
py p3fes_text.py extract extracted3 -o extracted3_text
echo [3/6] textures (.TMX to PNG)
py p3fes_tmx.py extracted3 -o extracted3_png
echo [4/6] audio (AFS split and WAV)
py p3fes_audio.py extracted3 -o audio3 --wav
echo [5/6] sound banks (.SE split and bank samples)
py p3fes_bed.py split extracted3 -o redo3_se_report.txt
py p3fes_bed.py banks extracted3 -o redo3_bank_report.txt
echo [6/6] counts
(
echo scripts_txt3:
dir /s /b scripts_txt3 ^| find /c /v ""
echo fields_out3 obj:
dir /s /b fields_out3\*.obj ^| find /c /v ""
echo fields_out3 png:
dir /s /b fields_out3\*.png ^| find /c /v ""
echo text files:
dir /s /b extracted3_text\*.txt ^| find /c /v ""
echo textures png:
dir /s /b extracted3_png\*.png ^| find /c /v ""
echo audio wav:
dir /s /b audio3\*.wav ^| find /c /v ""
echo sound bank wavs:
dir /s /b extracted3\*.wav ^| find /c ".SE.d"
) > redo3_counts.txt
echo Done. Send me redo3_counts.txt and any problems/report .txt files the tools wrote (for example fields_out3\fields_report.txt).
