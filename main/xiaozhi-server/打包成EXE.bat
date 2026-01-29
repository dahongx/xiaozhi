@echo off
chcp 65001 >nul
title XiaoZhi Server 打包工具

echo ============================================================
echo           XiaoZhi Server - EXE 打包工具
echo ============================================================
echo.
echo 请选择打包方式:
echo.
echo   [1] 打包主服务 (xiaozhi-server)
echo   [2] 打包气象模拟器 (weather-simulator)
echo   [3] 打包全部 (主服务 + 模拟器)
echo   [4] 安装打包依赖
echo   [5] 退出
echo.
set /p choice=请输入选项 (1-5): 

if "%choice%"=="1" goto main_only
if "%choice%"=="2" goto simulator_only
if "%choice%"=="3" goto build_all
if "%choice%"=="4" goto install
if "%choice%"=="5" goto end

echo 无效选项，请重新运行
goto end

:install
echo.
echo 正在安装打包依赖...
pip install pyinstaller
echo.
echo 依赖安装完成!
pause
goto end

:main_only
echo.
echo 正在打包主服务...
python build_exe_pyinstaller.py
pause
goto end

:simulator_only
echo.
echo 正在打包气象模拟器...
python build_simulator.py
pause
goto end

:build_all
echo.
echo ============================================================
echo [1/2] 正在打包主服务...
echo ============================================================
python build_exe_pyinstaller.py
if %errorlevel% neq 0 (
    echo 主服务打包失败!
    pause
    goto end
)

echo.
echo ============================================================
echo [2/2] 正在打包气象模拟器...
echo ============================================================
python build_simulator.py
if %errorlevel% neq 0 (
    echo 气象模拟器打包失败!
    pause
    goto end
)

echo.
echo ============================================================
echo 全部打包完成!
echo 输出目录: dist\
echo ============================================================
pause
goto end

:end
