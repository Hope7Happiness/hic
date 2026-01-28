from pathlib import Path
import tempfile
import pytest

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


@pytest.mark.asyncio
async def test_read_write_edit_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )

        file_path = tmp_path / "sample.txt"

        # Write
        result_write = await write(str(file_path), "hello\nworld", ctx)
        assert result_write.is_success
        assert file_path.exists()

        # Read first line
        result_read = await read(str(file_path), ctx, offset=0, limit=1)
        assert result_read.is_success
        assert "00001| hello" in result_read.output

        # Edit
        result_edit = await edit(str(file_path), "hello", "hi", ctx, replace_all=False)
        assert result_edit.is_success
        assert "hi" in file_path.read_text()


@pytest.mark.asyncio
async def test_read_binary_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"]}
        )

        bin_path = tmp_path / "bin.dat"
        bin_path.write_bytes(b"\x00\x01\x02")

        result = await read(str(bin_path), ctx)
        assert result.is_error
        title = result.title or ""
        err = result.error_message or ""
        assert "Binary" in title or "Binary" in err


@pytest.mark.asyncio
async def test_edit_no_match_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "file.txt"
        file_path.write_text("abc")

        result = await edit(str(file_path), "zzz", "yyy", ctx)
        assert result.is_error
        title = result.title or ""
        err = result.error_message or ""
        assert "Replacement failed" in title or "Replacement failed" in err


@pytest.mark.asyncio
async def test_read_pagination_multiple_pages():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "big.txt"
        content = "\n".join([f"line {i}" for i in range(30)])
        await write(str(file_path), content, ctx)

        first_page = await read(str(file_path), ctx, offset=0, limit=10)
        second_page = await read(str(file_path), ctx, offset=10, limit=10)

        assert first_page.is_success and second_page.is_success
        assert "00001| line 0" in first_page.output
        assert "00011| line 10" in second_page.output
        assert "more lines" in first_page.output


@pytest.mark.asyncio
async def test_edit_replace_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "dup.txt"
        file_path.write_text("foo\nfoo\nbar\nfoo\n")

        # replace_all should change all occurrences
        result = await edit(str(file_path), "foo", "baz", ctx, replace_all=True)
        assert result.is_success
        text = file_path.read_text()
        assert text.count("baz") == 3
        assert "foo" not in text


@pytest.mark.asyncio
async def test_edit_indentation_flexible():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "indent.py"
        file_path.write_text("def foo():\n    return 1\n")

        old = "def foo():\n\treturn 1"
        new = "def foo():\n    return 2"

        result = await edit(str(file_path), old, new, ctx)
        assert result.is_success
        assert "return 2" in file_path.read_text()


@pytest.mark.asyncio
async def test_edit_escape_normalized():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "escape.txt"
        file_path.write_text("line1\nline2\n")

        old = "line1\\nline2"
        new = "line1\\nline3"

        result = await edit(str(file_path), old, new, ctx)
        assert result.is_success
        assert "line3" in file_path.read_text()


@pytest.mark.asyncio
async def test_edit_block_anchor():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "block.txt"
        file_path.write_text("start\nalpha\nbeta\nend\n")

        old = "start\nalpha\nend"
        new = "start\nchanged\nend"

        result = await edit(str(file_path), old, new, ctx)
        assert result.is_success
        assert "changed" in file_path.read_text()


@pytest.mark.asyncio
async def test_edit_lock_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = create_auto_approve_context(
            working_directory=tmpdir, patterns={"read": ["*"], "write": ["*"]}
        )
        file_path = Path(tmpdir) / "locked.txt"
        file_path.write_text("hello")

        lock_path = Path(str(file_path) + ".lock")
        lock_path.write_text("locked")

        result = await edit(
            str(file_path),
            "hello",
            "hi",
            ctx,
            lock_timeout=0.1,
        )
        assert result.is_error
        title = result.title or ""
        err = result.error_message or ""
        assert "locked" in title.lower() or "locked" in err.lower()
