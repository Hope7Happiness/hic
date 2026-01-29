"""
Webfetch tool for HTTP content retrieval.
"""

from __future__ import annotations

from typing import Optional
import json
from xml.dom import minidom
from pathlib import Path
import importlib.util
import urllib.parse


agent_dir = Path(__file__).parent.parent


def _load_agent_module(module_name: str, file_name: str):
    module_path = agent_dir / file_name
    spec = importlib.util.spec_from_file_location(f"agent.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


permissions_mod = _load_agent_module("permissions", "permissions.py")
tool_result_mod = _load_agent_module("tool_result", "tool_result.py")

PermissionType = permissions_mod.PermissionType
PermissionRequest = permissions_mod.PermissionRequest
PermissionDeniedError = permissions_mod.PermissionDeniedError
ToolResult = tool_result_mod.ToolResult


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


def _validate_url(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "URL must start with http or https"
    if not parsed.netloc:
        return "URL missing host"
    return None


def _parse_content_type(content_type: str) -> tuple[str, Optional[str]]:
    if not content_type:
        return "", None
    parts = [p.strip() for p in content_type.split(";") if p.strip()]
    mime = parts[0].lower() if parts else ""
    charset = None
    for part in parts[1:]:
        if part.lower().startswith("charset="):
            charset = part.split("=", 1)[-1].strip()
            break
    return mime, charset


def _is_binary_mime(mime: str) -> bool:
    if not mime:
        return False
    if mime.startswith(("image/", "audio/", "video/")):
        return True
    if mime in {"application/octet-stream", "application/pdf"}:
        return True
    return False


async def webfetch(
    url: str,
    ctx,
    format: str = "markdown",
    timeout: int = 30,
):
    """
    Fetch web content and convert to requested format.

    Args:
        url: URL to fetch
        ctx: Execution context
        format: markdown|text|html
        timeout: seconds
    """
    try:
        format = (format or "markdown").lower()
        if format not in {"markdown", "text", "html"}:
            return ToolResult.from_error(
                "Invalid format",
                f"Unsupported format: {format}",
                url=url,
            )

        url_error = _validate_url(url)
        if url_error:
            return ToolResult.from_error("Invalid URL", url_error, url=url)

        await ctx.ask(
            PermissionRequest(
                permission=PermissionType.WEBFETCH,
                patterns=[url],
                metadata={"url": url, "format": format, "timeout": timeout},
                description=f"Fetch URL: {url}",
            )
        )

        ctx.check_abort()

        try:
            import requests
        except Exception as e:
            return ToolResult.from_error(
                "Missing dependency",
                f"requests is required: {e}",
                url=url,
            )

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json,*/*",
        }

        response = requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=True, stream=True
        )
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > 5 * 1024 * 1024:
                return ToolResult.from_error(
                    "Response too large",
                    f"Response exceeds 5MB: {content_length} bytes",
                    url=url,
                    size_bytes=int(content_length),
                )

        max_bytes = 5 * 1024 * 1024
        chunks = []
        size_bytes = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                return ToolResult.from_error(
                    "Response too large",
                    f"Response exceeds 5MB: {size_bytes} bytes",
                    url=url,
                    size_bytes=size_bytes,
                )
            chunks.append(chunk)

        content_bytes = b"".join(chunks)
        if size_bytes > 5 * 1024 * 1024:
            return ToolResult.from_error(
                "Response too large",
                f"Response exceeds 5MB: {size_bytes} bytes",
                url=url,
                size_bytes=size_bytes,
            )

        content_type = response.headers.get("content-type", "")
        mime_type, charset = _parse_content_type(content_type)
        is_binary = _is_binary_mime(mime_type)
        if is_binary:
            return ToolResult.from_error(
                "Binary content rejected",
                f"Unsupported content-type: {mime_type}",
                url=url,
                content_type=content_type,
                mime_type=mime_type,
                is_binary=True,
            )
        encoding = charset or "utf-8"
        text = content_bytes.decode(encoding, errors="replace")
        format_applied = format

        if format == "html":
            output = text
        elif format == "text":
            if "html" in mime_type:
                try:
                    import importlib

                    bs4 = importlib.import_module("bs4")
                    BeautifulSoup = getattr(bs4, "BeautifulSoup")
                except Exception as e:
                    return ToolResult.from_error(
                        "Missing dependency",
                        f"beautifulsoup4 is required: {e}",
                        url=url,
                    )
                soup = BeautifulSoup(text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                output = soup.get_text(separator="\n", strip=True)
            elif "json" in mime_type:
                try:
                    output = json.dumps(json.loads(text), indent=2)
                    format_applied = "json"
                except Exception:
                    output = text
            elif "xml" in mime_type:
                try:
                    output = minidom.parseString(text).toprettyxml()
                    format_applied = "xml"
                except Exception:
                    output = text
            else:
                output = text
        else:
            if "html" in mime_type:
                try:
                    import importlib

                    html2text = importlib.import_module("html2text")
                    HTML2Text = getattr(html2text, "HTML2Text")
                except Exception as e:
                    return ToolResult.from_error(
                        "Missing dependency",
                        f"html2text is required: {e}",
                        url=url,
                    )
                h = HTML2Text()
                h.ignore_links = False
                h.ignore_images = False
                h.ignore_emphasis = False
                output = h.handle(text)
            elif "json" in mime_type:
                try:
                    output = json.dumps(json.loads(text), indent=2)
                    format_applied = "json"
                except Exception:
                    output = text
            elif "xml" in mime_type:
                try:
                    output = minidom.parseString(text).toprettyxml()
                    format_applied = "xml"
                except Exception:
                    output = text
            else:
                output = text

        truncated, trunc_meta = ctx.truncate_output(output, context="webfetch output")

        return ToolResult.success(
            f"Fetched {url}",
            truncated,
            url=url,
            final_url=response.url,
            status_code=response.status_code,
            content_type=content_type,
            mime_type=mime_type,
            charset=charset,
            is_binary=is_binary,
            size_bytes=size_bytes,
            format=format,
            format_applied=format_applied,
            **trunc_meta,
        )

    except PermissionDeniedError as e:
        return ToolResult.from_error("Permission denied", str(e), url=url)
    except Exception as e:
        return ToolResult.from_error(
            "Webfetch failed", str(e), url=url, error_type=type(e).__name__
        )
