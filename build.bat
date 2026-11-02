@echo off
rem ============================================================
rem  Build TicketGen.exe (PyInstaller, single file, no console)
rem  Run from the project root:  build.bat
rem ============================================================
rem  The file is ASCII-only on purpose: cmd.exe breaks on UTF-8 text.

setlocal
cd /d "%~dp0"

echo [1/4] Checking dependencies...
py -m poetry install --no-interaction
if errorlevel 1 goto :error

echo [2/4] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TicketGen.spec del /q TicketGen.spec

echo [3/4] Building TicketGen.exe...
py -m poetry run pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name TicketGen ^
    --icon "ticketgen\views\icons\app_icon.ico" ^
    --add-data "ticketgen\views\icons;ticketgen\views\icons" ^
    main.py
if errorlevel 1 goto :error

echo [4/4] Preparing the dist folder...
rem Test database and CSV example are copied next to the exe for the demo.
if exist tickets.db copy /y tickets.db dist\tickets.db >nul
if exist examples xcopy /e /i /y examples dist\examples >nul

echo.
echo Done: dist\TicketGen.exe
echo The program is portable: copy the contents of dist to any folder or USB drive.
exit /b 0

:error
echo.
echo BUILD FAILED. See the messages above.
exit /b 1
