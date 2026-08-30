@echo off
cd /d %~dp0
start "" http://localhost:8020/
python -m http.server 8020
