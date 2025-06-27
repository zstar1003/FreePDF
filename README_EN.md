<div align="center">
  <img src="assets/logo_with_txt.png" width="400" alt="FreePDF">
</div>

<div align="center">
  <img src="https://img.shields.io/badge/version-2.0.0-blue" alt="version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL3.0-green" alt="license"></a>
  <h4>
    <a href="README.md">🇨🇳 中文</a>
    <span> | </span>
    <a href="README_EN.md">🇬🇧 English</a>
  </h4>
</div>

## 🌟 Introduction

A free PDF literature translation tool that makes reading English literature as easy as drinking water.


## 🏗️ Demo

[![FreePDF: Make reading English literature as easy as drinking water](https://i0.hdslb.com/bfs/archive/43c920704c379c27424211f3edfc1657369dfd66.jpg@672w_378h_1c.avif)](https://www.bilibili.com/video/BV1hcKfzEE9e)


## 📦 Usage

- Windows users:

  Download the installer directly: https://github.com/zstar1003/FreePDF/releases/download/v2.0.0/FreePDF_v2.0.0_Setup.exe

  Alternative link: https://pan.baidu.com/s/1KChVlJHMGML46YB4K8aMfg?pwd=8888 (Access code: 8888)

- Other system users:

  No installer provided. Please install the required environment and run `main.py` with Python.

After translation, the PDF files will generate `-dual.pdf` (bilingual version) and `test-mono.pdf` (Chinese translation only) in the corresponding directory.

## 📥 Configuration

Supports four optional translation engines, which can be configured through `Translation Settings`.

- 1. Bing Translator (Default)
     Select translation engine as bing, no additional parameters required

- 2. Google Translate
     Select translation engine as google, no additional parameters required

- 3. Silicon Flow Translator
     Select translation engine as silicon, requires additional configuration of [Silicon Flow](https://cloud.siliconflow.cn/i/bjDoFhPf) API Key and specific chat model.

- 4. Ollama Translator
     Select translation engine as ollama, first deploy local chat model through ollama, and configure ollama address and specific chat model.

Supports two translation modes: Chinese to English, English to Chinese, which can be set through `Source Language` and `Target Language`.

## 📮 Communication & Feedback

If you have any questions, feel free to submit an issue or contact me directly on WeChat: zstar1003 for feedback.

## 🚀 Acknowledgments

This project is developed based on the following open source projects:

- [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate)

- [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt)

- [pdf.js](https://github.com/mozilla/pdf.js) 