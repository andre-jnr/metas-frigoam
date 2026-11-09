@echo off
rem Abre o instalador do GitHub Actions runner como Administrador (pede confirmacao do Windows)
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File \"%~dp0instalar-runner.ps1\"'"
