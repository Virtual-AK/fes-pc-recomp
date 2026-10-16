@echo off
rem Reruns only the script-based checks on extracted3 and scripts_txt3 (after the tool update that accepts script_names.txt names).
rem Run it from the folder that holds the p3fes_*.py tools (C:\p3fes). Outputs go to the folder rerun3.
if not exist rerun3 mkdir rerun3
set PACK=extracted3\DATA.CVM\FIELD\PACK
echo [1/6] entrycount
py p3fes_field.py entrycount scripts_txt3 %PACK% -o rerun3\entrycount.txt
echo [2/6] doornorec
py p3fes_field.py doornorec scripts_txt3 %PACK% -o rerun3\doornorec.txt
echo [3/6] hbinrecs
py p3fes_field.py hbinrecs scripts_txt3 %PACK% -o rerun3\hbinrecs.txt
echo [4/6] eventvariants
py p3fes_field.py eventvariants scripts_txt3 %PACK% -o rerun3\eventvariants.txt
echo [5/6] doorwhere
py p3fes_field.py doorwhere scripts_txt3 %PACK% -o rerun3\doorwhere.txt
echo [6/6] callprocs
py p3fes_field.py callprocs scripts_txt3 field_137 field_360 field_33 -o rerun3\callprocs.txt
echo.
echo Done. Send me entrycount.txt, doornorec.txt, hbinrecs.txt, eventvariants.txt, doorwhere.txt and callprocs.txt from rerun3.
pause
