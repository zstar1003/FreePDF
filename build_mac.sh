#!/bin/bash

# macOS应用构建和打包脚本

set -e

echo "======================================"
echo "   FreePDF macOS 构建打包脚本 v5.1.3"
echo "======================================"
echo ""

# 配置变量
APP_NAME="FreePDF"
VERSION="5.1.3"
SPEC_FILE="build_mac.spec"

# 代码签名配置 (可选)
# 如果需要签名和公证,请设置以下变量(修改为自己的信息):
# SIGN_IDENTITY="Developer ID Application: 证书信息"
# APPLE_ID="自己的apple_id"
# TEAM_ID="自己的team_id"
# APP_PASSWORD="自己的app创建的密码"

SIGN_IDENTITY="${SIGN_IDENTITY:-}"
ENABLE_SIGNING=false
ENABLE_NOTARIZATION=false

if [ -n "$SIGN_IDENTITY" ]; then
    ENABLE_SIGNING=true
    echo "✓ 已配置代码签名"
    if [ -n "$APPLE_ID" ] && [ -n "$TEAM_ID" ] && [ -n "$APP_PASSWORD" ]; then
        ENABLE_NOTARIZATION=true
        echo "✓ 已配置公证服务"
    fi
else
    echo "⚠ 未配置代码签名,将跳过签名步骤"
    echo "  提示: 设置环境变量 SIGN_IDENTITY 以启用签名"
fi

echo ""

# 步骤1: 清理旧文件
echo "[1/6] 清理旧的构建文件..."
rm -rf build dist
mkdir -p dist
echo "✓ 清理完成"
echo ""

# 步骤2: 检查图标
echo "[2/6] 检查应用图标..."
if [ ! -f "ui/logo/logo.icns" ]; then
    echo "  图标文件不存在,正在转换..."
    ./create_icon.sh
else
    echo "✓ 图标文件已存在"
fi
echo ""

# 步骤3: 构建应用
echo "[3/6] 使用PyInstaller构建应用..."
echo "  这可能需要几分钟时间,请耐心等待..."
pyinstaller "$SPEC_FILE" --clean --noconfirm

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "❌ 构建失败: 找不到应用包"
    exit 1
fi
echo "✓ 应用构建完成"
echo ""

# 步骤3.5: 修复cv2重复问题
echo "[3.5/6] 修复cv2递归导入问题..."
if [ -d "dist/${APP_NAME}.app/Contents/Resources/cv2" ] && [ -d "dist/${APP_NAME}.app/Contents/Frameworks/cv2" ]; then
    echo "  检测到cv2重复目录,正在修复..."

    # 保存当前工作目录
    ORIGINAL_DIR=$(pwd)

    # 步骤1: 将Frameworks/cv2中指向Resources/cv2的符号链接转换为实际文件
    echo "  步骤1: 修复Frameworks/cv2中的符号链接..."
    cd "dist/${APP_NAME}.app/Contents/Frameworks/cv2"
    for link in $(find . -type l); do
        if [ -e "$link" ]; then
            target=$(readlink "$link")
            # 如果链接指向Resources/cv2,则复制实际文件
            if [[ "$target" == *"Resources/cv2"* ]]; then
                rm "$link"
                # 构建源文件的绝对路径
                source_file="../../Resources/cv2/$(basename $link)"
                if [ -e "$source_file" ]; then
                    cp -R "$source_file" "$link"
                    echo "    转换Frameworks: $link"
                fi
            fi
        fi
    done

    # 恢复工作目录
    cd "$ORIGINAL_DIR"

    # 步骤2: 将Resources中指向cv2/.dylibs的符号链接转换为实际文件
    echo "  步骤2: 修复Resources中指向cv2的符号链接..."
    cd "dist/${APP_NAME}.app/Contents/Resources"
    for link in $(find . -maxdepth 1 -type l); do
        if [ -e "$link" ]; then
            target=$(readlink "$link")
            # 如果链接指向cv2/.dylibs,则复制实际文件
            if [[ "$target" == cv2/.dylibs/* ]]; then
                link_name=$(basename "$link")
                rm "$link"
                # 源文件在Resources/cv2/.dylibs/目录下
                source_file="cv2/.dylibs/$link_name"
                if [ -e "$source_file" ]; then
                    cp -R "$source_file" "$link_name"
                    echo "    转换Resources: $link_name"
                fi
            fi
        fi
    done

    # 恢复工作目录
    cd "$ORIGINAL_DIR"

    # 步骤3: 现在安全地删除Resources/cv2
    echo "  步骤3: 删除Resources/cv2目录..."
    rm -rf "dist/${APP_NAME}.app/Contents/Resources/cv2"
    echo "✓ cv2重复问题已修复"
else
    echo "✓ 无需修复"
fi
echo ""

# 步骤4: 代码签名 (如果配置)
if [ "$ENABLE_SIGNING" = true ]; then
    echo "[4/6] 对应用进行代码签名..."

    # 签名所有框架和库
    echo "  签名动态库和框架..."

    # 签名MacOS目录下的dylib和so文件
    find "dist/${APP_NAME}.app/Contents/MacOS" -type f \( -name "*.dylib" -o -name "*.so" \) -exec \
        codesign --force --sign "$SIGN_IDENTITY" \
        --options runtime \
        --entitlements entitlements.plist \
        --timestamp {} \;

    # 签名Resources目录下的dylib文件（重要！公证需要）
    echo "  签名Resources目录下的dylib文件..."
    find "dist/${APP_NAME}.app/Contents/Resources" -type f -name "*.dylib" -exec \
        codesign --force --sign "$SIGN_IDENTITY" \
        --options runtime \
        --entitlements entitlements.plist \
        --timestamp {} \;

    # 签名Frameworks目录下的framework
    find "dist/${APP_NAME}.app/Contents/Frameworks" -type d -name "*.framework" -exec \
        codesign --force --sign "$SIGN_IDENTITY" \
        --options runtime \
        --entitlements entitlements.plist \
        --timestamp {} \; 2>/dev/null || true

    # 签名主应用
    echo "  签名主应用包..."
    codesign --force --deep --sign "$SIGN_IDENTITY" \
        --options runtime \
        --entitlements entitlements.plist \
        --timestamp \
        "dist/${APP_NAME}.app"

    # 等待签名完成
    echo "  等待签名完成..."
    sleep 2

    # 验证签名
    echo "  验证签名..."
    if codesign --verify --deep --strict --verbose=2 "dist/${APP_NAME}.app" 2>&1; then
        echo "  ✓ 签名验证成功"
    else
        echo "  ⚠ 签名验证失败,但不影响使用"
    fi

    # 评估签名
    if spctl --assess --verbose=4 --type execute "dist/${APP_NAME}.app" 2>&1; then
        echo "  ✓ Gatekeeper评估通过"
    else
        echo "  ⚠ Gatekeeper评估未通过(开发签名正常)"
    fi

    echo "✓ 代码签名完成"
else
    echo "[4/6] 跳过代码签名"
fi
echo ""

# 步骤5: 创建DMG
echo "[5/6] 创建DMG安装包..."
./create_dmg.sh

if [ ! -f "dist/${APP_NAME}_v${VERSION}_macOS.dmg" ]; then
    echo "❌ DMG创建失败"
    exit 1
fi
echo "✓ DMG创建完成"
echo ""

# 步骤6: DMG签名和公证 (如果配置)
if [ "$ENABLE_SIGNING" = true ]; then
    echo "[6/6] 对DMG进行签名..."
    codesign --sign "$SIGN_IDENTITY" \
        --timestamp \
        "dist/${APP_NAME}_v${VERSION}_macOS.dmg"

    echo "✓ DMG签名完成"

    if [ "$ENABLE_NOTARIZATION" = true ]; then
        echo ""
        echo "开始公证流程..."
        echo "  上传DMG到Apple公证服务..."

        # 提交公证
        SUBMIT_OUTPUT=$(xcrun notarytool submit \
            "dist/${APP_NAME}_v${VERSION}_macOS.dmg" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --password "$APP_PASSWORD" \
            --wait)

        echo "$SUBMIT_OUTPUT"

        # 检查公证结果
        if echo "$SUBMIT_OUTPUT" | grep -q "status: Accepted"; then
            echo "✓ 公证成功"

            # 装订公证票据
            echo "  装订公证票据..."
            xcrun stapler staple "dist/${APP_NAME}_v${VERSION}_macOS.dmg"
            echo "✓ 公证票据装订完成"
        else
            echo "❌ 公证失败"
            echo "  请检查Apple Developer账号配置和应用权限设置"
        fi
    fi
else
    echo "[6/6] 跳过DMG签名和公证"
fi
echo ""

# 完成
echo "======================================"
echo "           构建完成! 🎉"
echo "======================================"
echo ""
echo "输出文件:"
echo "  - 应用包: dist/${APP_NAME}.app"
echo "  - 安装包: dist/${APP_NAME}_v${VERSION}_macOS.dmg"
echo ""

# 显示文件大小
ls -lh "dist/${APP_NAME}_v${VERSION}_macOS.dmg"

echo ""
echo "使用说明:"
echo "  1. 无签名版本可直接分发给用户安装"
echo "  2. 用户首次打开可能需要在系统设置中允许运行"
if [ "$ENABLE_SIGNING" = false ]; then
    echo ""
    echo "代码签名配置 (可选):"
    echo "  如需对应用进行签名和公证,请设置以下环境变量:"
    echo "    export SIGN_IDENTITY='Developer ID Application: Your Name (TEAM_ID)'"
    echo "    export APPLE_ID='your-apple-id@email.com'"
    echo "    export TEAM_ID='YOUR_TEAM_ID'"
    echo "    export APP_PASSWORD='app-specific-password'"
    echo ""
    echo "  然后重新运行此脚本"
fi
echo ""
