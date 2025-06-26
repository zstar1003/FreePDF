@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ======================================
echo    FreePDF - Google翻译连通性检测
echo ======================================
echo.

echo 正在检测Google翻译服务...
echo.

REM 检测translate.google.com/m
echo [1/1] 检测 translate.google.com/m...
curl -I "https://translate.google.com/m" --connect-timeout 10 >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ translate.google.com/m 可以访问
    set google_main=1
) else (
    echo ✗ translate.google.com/m 无法访问
    set google_main=0
)


echo.
echo ======================================
echo              检测结果
echo ======================================

set /a total_score=!google_main!

if !total_score! equ 1 (
    echo 状态: ✓ 连接正常
    echo 说明: Google翻译服务完全可用，FreePDF可以正常使用Google翻译功能
    echo 建议: 无需额外设置
) else (
    echo 状态: ✗ 无法连接
    echo 说明: 无法访问Google翻译服务
    echo 建议: 1. 检查网络连接
    echo       2. 检查防火墙/代理设置
    echo       3. 尝试使用科学上网
)



echo 检测完成！按任意键退出...
pause >nul