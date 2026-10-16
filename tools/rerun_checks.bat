@echo off
rem Reruns the field checks on the new extraction (extracted3, made with the fixed unpacker).
rem Run it from the folder that holds the p3fes_*.py tools (C:\p3fes). Outputs go to the folder rerun3.
rem It takes a few minutes. Nothing here changes your game files.
if not exist rerun3 mkdir rerun3
set PACK=extracted3\DATA.CVM\FIELD\PACK
echo [1/12] split the .FPC containers
py p3fes_field.py split %PACK% -o rerun3\split3.txt
echo [2/12] export the scripts (scripts_txt3)
py p3fes_bf.py export extracted3 --exe extracted3\SLUS_216.21 -o scripts_txt3
echo [3/12] emptyfiles
py p3fes_field.py emptyfiles %PACK% -o rerun3\emptyfiles.txt
echo [4/12] entrycount
py p3fes_field.py entrycount scripts_txt3 %PACK% -o rerun3\entrycount.txt
echo [5/12] doornorec
py p3fes_field.py doornorec scripts_txt3 %PACK% -o rerun3\doornorec.txt
echo [6/12] hbinw5
py p3fes_field.py hbinw5 %PACK% -o rerun3\hbinw5.txt
echo [7/12] hbinrecs
py p3fes_field.py hbinrecs scripts_txt3 %PACK% -o rerun3\hbinrecs.txt
echo [8/12] hbinprocs
py p3fes_field.py hbinprocs scripts_txt3 %PACK% -o rerun3\hbinprocs.txt
echo [9/12] eventvariants
py p3fes_field.py eventvariants scripts_txt3 %PACK% -o rerun3\eventvariants.txt
echo [10/12] doorwhere
py p3fes_field.py doorwhere scripts_txt3 %PACK% -o rerun3\doorwhere.txt
echo [11/12] callprocs
py p3fes_field.py callprocs scripts_txt3 field_137 field_360 -o rerun3\callprocs.txt
echo [12/12] fbnvariants
py p3fes_field.py fbnvariants %PACK% -o rerun3\fbnvariants.txt
echo.
echo Done. Send me the files in the rerun3 folder (not scripts_txt3: it holds game text).
pause
