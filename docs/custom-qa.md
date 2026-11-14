# 自定义问答 API 地址 / Custom Q&A endpoints

自定义问答使用 OpenAI 兼容的聊天请求与 SSE 流式响应格式。连接测试和实际问答使用同一地址解析规则：

| CUSTOM_HOST | 请求地址 / Request URL |
| --- | --- |
| https://example.com | https://example.com/v1/chat/completions |
| https://example.com/v1 | https://example.com/v1/chat/completions |
| https://example.com/api/v3 | https://example.com/api/v3/chat/completions |
| https://example.com/proxy/v1 | https://example.com/proxy/v1/chat/completions |
| https://example.com/chat/completions | 原样使用 / unchanged |
| https://example.com/v1/chat/completions | 原样使用 / unchanged |

尾部斜杠会去除，查询参数保留。使用 http:// 或 https:// 完整地址，并填写 CUSTOM_MODEL。API Key 按服务商要求填写。裸主机地址保留原有问答行为，默认添加 /v1/chat/completions；如果服务商使用无 /v1 的接口，请填写完整 /chat/completions 地址。

Custom Q&A requires an OpenAI-compatible JSON request and SSE streaming response. Supply a host, API base path, or full URL ending in /chat/completions. Trailing slashes are normalized and query parameters are preserved. Bare hosts retain the existing Q&A default /v1/chat/completions. To use an unversioned endpoint, enter the full /chat/completions URL.

对于不以 /chat/completions 结尾的兼容接口，在“完整接口 URL”中填写服务商的完整地址（保存为 qa_engine.envs.CUSTOM_API_URL）。该项优先于 Host，路径和查询参数原样保留，不会自动追加任何内容；留空则使用上述 Host 规则。

For an OpenAI-compatible endpoint with an arbitrary path, set “完整接口 URL” (qa_engine.envs.CUSTOM_API_URL) to the exact URL. This overrides Host and preserves the path and query without adding a suffix. Leave it empty to use Host normalization.

本次规则仅用于自定义问答，不改变翻译引擎、Ollama 或 Silicon 的配置。连接测试是非流式的小请求；连接成功不保证模型支持流式响应或有足够的上下文额度。

These rules apply only to custom Q&A, not translation, Ollama, or Silicon. The connection test is a small non-streaming request; success does not guarantee streaming support or enough context capacity.

## Regression tests

QT_QPA_PLATFORM=offscreen python -m pytest tests/test_qa_endpoint.py -q

The tests exercise the real connection-test worker and Q&A handler with mocked HTTP requests. They do not require API keys or contact any provider.
