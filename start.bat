@echo off
chcp 65001 >nul
REM ============================================
REM  知识库管理工具 - 离线启动脚本
REM  双击即可运行，无需安装 Python 或任何依赖
REM ============================================
cd /d "%~dp0"
runtime\python\python.exe app\main.py
if errorlevel 1 pause
