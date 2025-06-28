<div align="center">
  <img src="assets/logo_with_txt.png" width="400" alt="FreePDF">
</div>

<div align="center">
  <img src="https://img.shields.io/badge/版本-2.0.0-blue" alt="版本">
  <a href="LICENSE"><img src="https://img.shields.io/badge/许可证-AGPL3.0-green" alt="许可证"></a>
  <h4>
    <a href="README.md">🇨🇳 中文</a>
    <span> | </span>
    <a href="README_EN.md">🇬🇧 English</a>
  </h4>
</div>

## 🌟 简介

一个免费的PDF文献翻译工具，让看英文文献像喝水一样简单。


## 🏗️ 效果演示

[![FreePDF：让看英文文献像喝水一样简单](https://i0.hdslb.com/bfs/archive/43c920704c379c27424211f3edfc1657369dfd66.jpg@672w_378h_1c.avif)](https://www.bilibili.com/video/BV1hcKfzEE9e)


## 📦 使用方式

- windows 用户:

  直接下载安装包：https://github.com/zstar1003/FreePDF/releases/download/v2.0.0/FreePDF_v2.0.0_Setup.exe

  备用链接：https://pan.baidu.com/s/1KChVlJHMGML46YB4K8aMfg?pwd=8888 (提取码: 8888)

- 其它系统用户:

  未提供安装包，可安装相关环境，用 python 运行 `main.py`。

翻译完的PDF文件，会在其对应目录下生成 `-dual.pdf`(双语对照文件) 和 `test-mono.pdf`(中文翻译文件)

## 📥 配置说明

支持四种可选翻译引擎，可通过`翻译配置`进行设置。

- 1. 必应翻译(默认)
     选择翻译引擎为bing，无需额外参数

- 2. 谷歌翻译
     选择翻译引擎为google，无需额外参数

- 3. 硅基翻译
     选择翻译引擎为silicon，需额外配置[硅基流动](https://cloud.siliconflow.cn/i/bjDoFhPf)API Key和具体聊天模型。

- 4. Ollama翻译
     选择翻译引擎为ollama，先通过ollama部署本地chat模型，并配置ollama地址和具体聊天模型。

支持两种翻译模式：中译英、英译中，可通过`原语言`和`目标语言`进行设置。

## 📮 常见问题

1. 支持图片型PDF吗，比如扫描件？

**回答：** 不支持，本质上是借助`pdf2zh`检测文本块内容，再进行翻译替换，图片型无法直接替换，会导致内容重合叠加。

2. 使用大模型翻译时，有些内容没有翻译？

**回答：** 低参数量的大模型本身的指令遵循能力很差，让它翻译，它可能不会完全听话，就会造成此现象。因此，本地用大模型翻译，必须保证大模型本身具备一定参数规模，建议7B以上。

如有其它问题，欢迎提交 issue 或 直接联系我的微信 zstar1003 反馈问题。

## 🛠️ 如何贡献

1. Fork本GitHub仓库
2. 将fork克隆到本地：  
`git clone git@github.com:<你的用户名>/FreePDF.git`
3. 创建本地分支：  
`git checkout -b my-branch`
4. 提交信息需包含充分说明：  
`git commit -m '提交信息需包含充分说明'`
5. 推送更改到GitHub（含必要提交信息）：  
`git push origin my-branch`
6. 提交PR等待审核

## 🚀 鸣谢

本项目基于以下开源项目开发：

- [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)

- [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt)

- [pdf.js](https://github.com/mozilla/pdf.js)

