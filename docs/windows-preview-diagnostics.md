# FreePDF 6.0 PDF 预览与支持日志

Windows 6.0 使用内置 Qt PDF 阅读器，安装包不包含 WebEngine，也不会启动 QtWebEngineProcess。之前日志中的 `0xC0000135` 表示 WebEngine 原生子进程无法加载 DLL；这次通过替换 Windows 阅读器解除该依赖，而不是要求使用者排障。

Mac 继续使用 PDF.js，预览失败会自动切换为 Qt PDF。预览状态记录实际 backend；`qt_pdf` 表示原生阅读器，`recovery` 记录自动切换原因。`document_loaded` 和 `first_page_rendered` 分别表示文档可读与实际页面渲染完成。

## 导出支持日志

在 **关于软件** 底部左侧点击 **导出日志**，与 **检查更新** 按钮相邻。选择 ZIP 保存位置即可，成功或失败信息直接显示，无额外诊断窗口。日志不自动上传。

日志自动记录启动/组件版本、窗口图标与原生库位置、PDF 加载、真实页面渲染、预览恢复、翻译以及 PDF 导出。每份日志约 5 MiB，保留当前及 3 份历史文件。ZIP 只含日志和诊断状态，不附带 PDF 或 API 配置；密钥字段及已登记密钥值会脱敏。

## 发布验证

Windows 构建检查 Qt6Pdf.dll、Qt6PdfWidgets.dll、PNG 图标以及 WebEngine 文件缺席；随后在干净 PATH、独立工作目录中验证双栏实际渲染，再将 NSIS 安装到含空格路径，重复运行同一验证。Mac 验证打包后的 PDF.js 和强制原生路径，并检查本机签名及 DMG。
