@echo off
rem Start the hub; pass extra flags through, e.g. start_hub.bat --public-url https://laptop.tailnet.ts.net
python "%~dp0hub.py" %*
