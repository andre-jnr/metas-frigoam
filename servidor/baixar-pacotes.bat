@echo off
rem Baixa os pacotes Python para servidor\pacotes (rode num computador com boa internet)
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0baixar-pacotes.ps1"
