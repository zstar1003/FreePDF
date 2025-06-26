@echo off
echo 开始打包 FreePDF...

REM 清理之前的构建
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM 使用PyInstaller打包
pyinstaller build_exe.spec

REM 检查打包是否成功
if exist dist\FreePDF\FreePDF.exe (
    echo 打包成功！
    echo 可执行文件位置: dist\FreePDF\FreePDF.exe
) else (
    echo 打包失败！
)

pause 