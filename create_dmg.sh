#!/bin/bash

# DMG打包脚本

set -e

# 配置变量
APP_NAME="FreePDF"
VERSION="5.1.3"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="${APP_NAME}_v${VERSION}_macOS"
DMG_TEMP="${DMG_NAME}_temp.dmg"
DMG_FINAL="${DMG_NAME}.dmg"
VOLUME_NAME="${APP_NAME}"
BACKGROUND_IMAGE="assets/dmg_background.png"

# 检查app是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "错误: 找不到应用包 $APP_PATH"
    echo "请先运行 build_mac.sh 构建应用"
    exit 1
fi

echo "开始创建DMG安装包..."

# 删除旧的DMG文件
rm -f "dist/${DMG_TEMP}"
rm -f "dist/${DMG_FINAL}"

# 如果DMG已挂载,先卸载
if [ -d "$MOUNT_POINT" ]; then
    echo "检测到已挂载的DMG,正在卸载..."
    hdiutil detach "$MOUNT_POINT" 2>/dev/null || true
    sleep 1
fi

# 计算应用大小并创建临时DMG (增加50MB缓冲空间)
echo "计算应用大小..."
APP_SIZE=$(du -sm "$APP_PATH" | cut -f1)
DMG_SIZE=$((APP_SIZE + 50))
echo "应用大小: ${APP_SIZE}MB, DMG大小: ${DMG_SIZE}MB"

# 创建临时文件夹用于DMG内容
echo "准备DMG内容..."
DMG_TEMP_DIR="dist/dmg_temp"
rm -rf "$DMG_TEMP_DIR"
mkdir -p "$DMG_TEMP_DIR"

# 复制应用到临时文件夹
echo "复制应用..."
cp -R "$APP_PATH" "$DMG_TEMP_DIR/"

# 创建Applications链接
echo "创建Applications快捷方式..."
ln -s /Applications "$DMG_TEMP_DIR/Applications"

# 创建临时DMG
echo "创建临时DMG..."
hdiutil create -srcfolder "$DMG_TEMP_DIR" -volname "$VOLUME_NAME" -fs HFS+ \
    -fsargs "-c c=64,a=16,e=16" -format UDRW -size ${DMG_SIZE}m "dist/${DMG_TEMP}"

# 挂载DMG
echo "挂载DMG..."
DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "dist/${DMG_TEMP}" | \
    egrep '^/dev/' | sed 1q | awk '{print $1}')
MOUNT_POINT="/Volumes/${VOLUME_NAME}"

echo "挂载点: $MOUNT_POINT"
sleep 2

# 设置DMG窗口外观
echo "配置DMG窗口外观..."

# 使用AppleScript设置窗口属性
osascript <<EOD
tell application "Finder"
    tell disk "$VOLUME_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 1000, 450}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 128
        set position of item "${APP_NAME}.app" of container window to {150, 180}
        set position of item "Applications" of container window to {450, 180}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
EOD

# 确保所有更改已写入
echo "同步磁盘..."
sync
sleep 2

# 卸载DMG
echo "卸载DMG..."
hdiutil detach "$DEVICE"
sleep 2

# 转换为压缩的只读DMG
echo "转换为最终DMG..."
hdiutil convert "dist/${DMG_TEMP}" -format UDZO -imagekey zlib-level=9 -o "dist/${DMG_FINAL}"

# 删除临时文件
rm -f "dist/${DMG_TEMP}"
rm -rf "$DMG_TEMP_DIR"

if [ -f "dist/${DMG_FINAL}" ]; then
    echo "✅ DMG创建成功: dist/${DMG_FINAL}"
    ls -lh "dist/${DMG_FINAL}"
else
    echo "❌ DMG创建失败"
    exit 1
fi
