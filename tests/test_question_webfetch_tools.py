from pathlib import Path
import threading
import http.server
import socketserver
import pytest
import importlib.util
import sys


def import_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


agent_dir = Path(__file__).parent.parent / "agent"
context_module = import_module_from_path("agent_context", agent_dir / "context.py")
question_module = import_module_from_path(
    "agent_tools_question", agent_dir / "tools" / "question.py"
)
webfetch_module = import_module_from_path(
    "agent_tools_webfetch", agent_dir / "tools" / "webfetch.py"
)

create_auto_approve_context = context_module.create_auto_approve_context
question = question_module.question
webfetch = webfetch_module.webfetch


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/html":
            body = "<html><body><h1>Title</h1><p>Hello</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/text":
            body = "plain text"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/json":
            body = '{"ok": true, "count": 2}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/xml":
            body = "<root><item>1</item><item>2</item></root>"
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/bin":
            body = b"\x00\x01\x02"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


@pytest.fixture()
def http_server():
    with socketserver.TCPServer(("127.0.0.1", 0), _Handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            httpd.shutdown()


@pytest.mark.asyncio
async def test_question_single_choice():
    ctx = create_auto_approve_context(patterns={"question": ["*"]})

    def handler(prompt: str):
        return "1"

    ctx.set_user_input_handler(handler)

    questions = [
        {
            "header": "Choice",
            "question": "Pick one",
            "options": [
                {"label": "A", "description": "Option A"},
                {"label": "B", "description": "Option B"},
            ],
        }
    ]

    result = await question(questions, ctx)
    assert result.is_success
    assert result.metadata["answers"][0]["selected"] == ["A"]


@pytest.mark.asyncio
async def test_question_multi_choice_custom():
    ctx = create_auto_approve_context(patterns={"question": ["*"]})

    def handler(prompt: str):
        return "1, custom"

    ctx.set_user_input_handler(handler)

    questions = [
        {
            "header": "Multi",
            "question": "Pick",
            "options": [
                {"label": "A", "description": "Option A"},
                {"label": "B", "description": "Option B"},
            ],
            "multiple": True,
        }
    ]

    result = await question(questions, ctx)
    assert result.is_success
    assert result.metadata["answers"][0]["selected"] == ["A", "custom"]


@pytest.mark.asyncio
async def test_question_no_handler_error():
    ctx = create_auto_approve_context(patterns={"question": ["*"]})

    questions = [
        {
            "header": "Choice",
            "question": "Pick one",
            "options": [{"label": "A", "description": "Option A"}],
        }
    ]

    result = await question(questions, ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_webfetch_html_markdown(http_server):
    pytest.importorskip("html2text")
    ctx = create_auto_approve_context(patterns={"webfetch": ["*"]})
    url = f"{http_server}/html"

    result = await webfetch(url, ctx, format="markdown")
    assert result.is_success
    assert "Title" in result.output


@pytest.mark.asyncio
async def test_webfetch_text(http_server):
    ctx = create_auto_approve_context(patterns={"webfetch": ["*"]})
    url = f"{http_server}/text"

    result = await webfetch(url, ctx, format="text")
    assert result.is_success
    assert "plain text" in result.output


@pytest.mark.asyncio
async def test_webfetch_json(http_server):
    ctx = create_auto_approve_context(patterns={"webfetch": ["*"]})
    url = f"{http_server}/json"

    result = await webfetch(url, ctx, format="text")
    assert result.is_success
    assert '"ok"' in result.output


@pytest.mark.asyncio
async def test_webfetch_xml(http_server):
    ctx = create_auto_approve_context(patterns={"webfetch": ["*"]})
    url = f"{http_server}/xml"

    result = await webfetch(url, ctx, format="text")
    assert result.is_success
    assert "<root>" in result.output


@pytest.mark.asyncio
async def test_webfetch_binary_rejected(http_server):
    ctx = create_auto_approve_context(patterns={"webfetch": ["*"]})
    url = f"{http_server}/bin"

    result = await webfetch(url, ctx, format="text")
    assert result.is_error
