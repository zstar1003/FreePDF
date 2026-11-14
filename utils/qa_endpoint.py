"""Endpoint normalization shared by custom Q&A and its connection test."""

from urllib.parse import urlsplit, urlunsplit


def resolve_qa_endpoint(host: str, endpoint: str = None) -> str:
    """Resolve an OpenAI-compatible host, base URL, or chat endpoint.

    Bare hosts retain the historical Q&A default of /v1/chat/completions.
    A base path (for example /v1 or /api/v3) is preserved. An explicit
    /chat/completions endpoint is used unchanged, including its query.
    The optional exact endpoint override never receives a suffix.
    """
    if endpoint is not None and not isinstance(endpoint, str):
        raise ValueError("CUSTOM_API_URL 必须是完整的 http:// 或 https:// URL")
    if endpoint:
        parts = urlsplit(endpoint.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("CUSTOM_API_URL 必须是完整的 http:// 或 https:// URL")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    if not isinstance(host, str) or not host.strip():
        raise ValueError("自定义问答引擎需要 CUSTOM_HOST")
    parts = urlsplit(host.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("CUSTOM_HOST 必须是完整的 http:// 或 https:// URL")
    path = parts.path.rstrip("/")
    if not path:
        path = "/v1/chat/completions"
    elif not path.endswith("/chat/completions"):
        path += "/chat/completions"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))
