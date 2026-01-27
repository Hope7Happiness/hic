import asyncio
from pathlib import Path
import tempfile

import sys
import importlib.util


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
permissions_module = import_module_from_path(
    "agent_permissions", agent_dir / "permissions.py"
)
tool_result_module = import_module_from_path(
    "agent_tool_result", agent_dir / "tool_result.py"
)
read_module = import_module_from_path(
    "agent_tools_read", agent_dir / "tools" / "read.py"
)
write_module = import_module_from_path(
    "agent_tools_write", agent_dir / "tools" / "write.py"
)
edit_module = import_module_from_path(
    "agent_tools_edit", agent_dir / "tools" / "edit.py"
)


Context = context_module.Context
create_auto_approve_context = context_module.create_auto_approve_context
PermissionDeniedError = permissions_module.PermissionDeniedError
ToolResult = tool_result_module.ToolResult
read = read_module.read
write = write_module.write
edit = edit_module.edit


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_read_write_edit_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )

        file_path = tmp_path / "sample.txt"

        # Write
        result_write = run(write(str(file_path), "hello\nworld", ctx))
        assert result_write.is_success
        assert file_path.exists()

        # Read first line
        result_read = run(read(str(file_path), ctx, offset=0, limit=1))
        assert result_read.is_success
        assert "00001| hello" in result_read.output

        # Edit
        result_edit = run(edit(str(file_path), "hello", "hi", ctx, replace_all=False))
        assert result_edit.is_success
        assert "hi" in file_path.read_text()


def test_read_binary_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"]}
        )

        bin_path = tmp_path / "bin.dat"
        bin_path.write_bytes(b"\x00\x01\x02")

        result = run(read(str(bin_path), ctx))
        assert result.is_error
        title = result.title or ""
        err = result.error_message or ""
        assert "Binary" in title or "Binary" in err


def test_edit_no_match_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "file.txt"
        file_path.write_text("abc")

        result = run(edit(str(file_path), "zzz", "yyy", ctx))
        assert result.is_error
        title = result.title or ""
        err = result.error_message or ""
        assert "Replacement failed" in title or "Replacement failed" in err


def test_read_pagination_multiple_pages():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "big.txt"
        content = "\n".join([f"line {i}" for i in range(30)])
        run(write(str(file_path), content, ctx))

        first_page = run(read(str(file_path), ctx, offset=0, limit=10))
        second_page = run(read(str(file_path), ctx, offset=10, limit=10))

        assert first_page.is_success and second_page.is_success
        assert "00001| line 0" in first_page.output
        assert "00011| line 10" in second_page.output
        assert "more lines" in first_page.output


def test_edit_replace_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "dup.txt"
        file_path.write_text("foo\nfoo\nbar\nfoo\n")

        # replace_all should change all occurrences
        result = run(edit(str(file_path), "foo", "baz", ctx, replace_all=True))
        assert result.is_success
        text = file_path.read_text()
        assert text.count("baz") == 3
        assert "foo" not in text