# Windows PDF 预览空白：排查与日志

## 已确认的代码隐患

1. Windows 的 `build.spec` 原来使用 `('pdfjs', '.')`。PyInstaller 会把目录内容放进目标目录，因此产生 `_internal/web/viewer.html` 和 `_internal/build/pdf.mjs`，而控件查找 `_internal/pdfjs/web/viewer.html`。修正为 `('pdfjs', 'pdfjs')`；资源查找也兼容旧的平铺目录，并检查 viewer、CSS、主模块及 worker 是否完整。开发环境的资源路径不再依赖启动时的工作目录。
2. 控件手工拼接 `?file=...`，未把文件 URL 作为完整的查询参数编码；PDF.js 又对已经由 `URLSearchParams` 解码的参数执行一次 `decodeURIComponent`。例如 `A&B#C%.pdf` 中的 `&` 可变成参数分隔符，`#` 可变成 URL 片段，造成读错路径。现在用 `QUrl.fromLocalFile` 构造文件 URL，再编码查询参数；viewer 保留文件 URL 自身的百分号转义。
3. 控件原先在替换默认 page 之前设置关闭 2D canvas 加速，设置可能随旧 page 一起丢弃。现在在实际使用的自定义 page 上设置。

翻译引擎直接使用文件路径，与 Qt WebEngine/PDF.js 的读取及渲染流程独立，所以这些预览问题不会必然导致翻译失败。以上问题在源码及测试中得到验证，但不能据此断言某位 Windows 11 使用者的具体故障原因。显卡驱动、WebEngine 子进程启动或特定 PDF 的异常，需要现场日志确认。

发行包验证还发现：英文 Windows 启动器传入 cp1252 输出流时，旧依赖初始化 hook 的中文输出会抛出 `UnicodeEncodeError`，发生在主程序开始记录日志之前。Windows 打包现已先运行诊断 hook，处理继承的输出编码、捕获控制台及异常，再初始化依赖。`dependency runtime hooks starting` 可用于定位这段早期启动流程。

## 使用者提供日志

1. 使用重新打包的版本，在 Windows 11 上启动软件并重现问题。
2. 记录大概时间，等待约 30–35 秒，让预览超时诊断完成。翻译可以继续运行。
3. 打开 **引擎配置 → 诊断与日志 → 导出日志…**，保存 ZIP 并提供给开发者。导出不需要填写或保存引擎配置，也不需要启动翻译。
4. 若疑似显卡兼容问题，在同一界面勾选 **使用软件渲染**，关闭并重启软件，再用同一 PDF 重试并导出第二份日志。此选项会在 Qt 初始化前增加 `--disable-gpu`，可能降低性能；取消后重启可恢复。

日志保存在 `%LOCALAPPDATA%\FreePDF\logs`，单文件约 5 MiB，保留当前日志及 3 份历史文件。启动时即开始记录；翻译界面的“清空日志”不会清除这些诊断文件。日志不会自动上传。ZIP 仅包含运行环境、当前预览状态和近期日志，不附带 PDF、聊天记录或 API 配置文件；日志中可能有文件名、路径和异常信息，常见密钥字段及已登记的密钥值会脱敏。

## 开发者阅读日志

- `environment.json`：操作系统、Python/PyQt/Qt WebEngine 版本、打包模式、运行目录、Chromium 参数及软件渲染设置。
- `preview_state.json`：原文和译文各自的加载 ID、阶段、错误、页面数、尺寸和可见性；超时后包含 JS 状态、viewport 与 canvas 尺寸。实时生命周期记录以日志为准。
- `logs/freepdf.log*`：时间、会话 ID、进程、线程、组件及事件。`import=` 串联 UI 导入与翻译结果；`view=` 和 `load=` 区分原文、译文及每次预览请求。

| 日志现象 | 优先检查 |
| --- | --- |
| `PDF/resource access failed`、缺少 `viewer.html` 或 `pdf.worker.mjs` | 打包资源路径、安装是否完整、文件权限 |
| `navigation_status` 失败 | Qt 页面加载错误码、安装/启动路径 |
| HTML 成功，但没有 `viewer_initialized` | `resource_error`、JS 初始化异常、运行时能力和 Qt 版本 |
| `document_error` | PDF URL、文件读取、PDF 损坏/密码及 worker 错误 |
| `document_loaded`，但没有 `first_page_rendered` | 页面渲染错误、viewport/canvas 尺寸、视图是否隐藏、显卡兼容 |
| `renderer_terminated` | WebEngine 子进程退出码、Qt 消息、软件渲染对比 |
| `javascript_unresponsive` | 页面线程未响应、Qt 日志及进程异常 |
| 翻译成功，原文或译文的预览失败 | 沿该视图的 `load=` 查预览流程；不要把翻译成功当成渲染成功 |

## 验证记录

本地 macOS 测试使用 Python 3.12、PyQt6 6.9.1、Qt/WebEngine 6.9.1（先前也验证了 6.9.2）：验证 Windows 打包数据展开、特殊字符/盘符/UNC URL、开发与打包资源解析、日志轮转/脱敏/导出、设置入口，以及真实 Qt WebEngine 的 PDF 页面渲染、损坏 PDF 和缺失文件错误。Windows 发行包由 GitHub Actions 构建并运行回归测试；Windows 11 特定设备的故障仍需结合现场日志确认。

运行回归测试：

```sh
python -m pytest tests -q
```

Linux 无显示的 CI 可使用 `QT_QPA_PLATFORM=offscreen`；测试依赖 PyQt6、PyQt6-WebEngine、PyMuPDF、PyInstaller 和 pytest。测试不调用翻译 API。

参考：[PyInstaller 资源打包规则](https://pyinstaller.org/en/latest/spec-files.html#adding-data-files)、[Qt URL 查询编码](https://doc.qt.io/qt-6/qurlquery.html)、[Qt WebEngine 调试及 GPU 参数](https://doc.qt.io/qt-6/qtwebengine-debugging.html)。
