import os
from pathlib import Path
import importlib.util
import sys
import pytest


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
grep_module = import_module_from_path(
    "agent_tools_grep", agent_dir / "tools" / "grep.py"
)
glob_module = import_module_from_path(
    "agent_tools_glob", agent_dir / "tools" / "glob.py"
)
todo_module = import_module_from_path(
    "agent_tools_todo", agent_dir / "tools" / "todo.py"
)

create_auto_approve_context = context_module.create_auto_approve_context
grep = grep_module.grep
glob = glob_module.glob
todowrite = todo_module.todowrite
todoread = todo_module.todoread


@pytest.mark.asyncio
async def test_glob_orders_by_mtime(tmp_path: Path):
    ctx = create_auto_approve_context(
        working_directory=str(tmp_path), patterns={"read": ["*"]}
    )

    older = tmp_path / "older.txt"
    newer = tmp_path / "newer.txt"

    older.write_text("old")
    newer.write_text("new")

    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    result = await glob("*.txt", ctx, path=str(tmp_path))
    assert result.is_success

    lines = [line for line in result.output.splitlines() if line.strip()]
    assert lines[0].endswith("newer.txt")
    assert any(line.endswith("older.txt") for line in lines)


@pytest.mark.asyncio
async def test_grep_basic_match(tmp_path: Path):
    ctx = create_auto_approve_context(
        working_directory=str(tmp_path), patterns={"read": ["*"]}
    )

    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("hello world\nnope")
    file_b.write_text("nothing here\nhello again")

    result = await grep("hello", ctx, path=str(tmp_path), include="*.txt")
    assert result.is_success
    assert "a.txt" in result.output or "b.txt" in result.output
    assert result.metadata.get("match_count", 0) >= 2


@pytest.mark.asyncio
async def test_grep_invalid_regex_error(tmp_path: Path):
    ctx = create_auto_approve_context(
        working_directory=str(tmp_path), patterns={"read": ["*"]}
    )

    result = await grep("(", ctx, path=str(tmp_path))
    assert result.is_error


@pytest.mark.asyncio
async def test_todo_write_and_read():
    ctx = create_auto_approve_context(patterns={"todo": ["*"]})

    todos = [
        {
            "id": "t1",
            "content": "Write docs",
            "status": "pending",
            "priority": "high",
        },
        {
            "id": "t2",
            "content": "Add tests",
            "status": "in_progress",
            "priority": "medium",
        },
    ]

    write_result = await todowrite(todos, ctx)
    assert write_result.is_success
    assert write_result.metadata.get("count") == 2

    read_result = await todoread(ctx)
    assert read_result.is_success
    assert "Write docs" in read_result.output


@pytest.mark.asyncio
async def test_todo_invalid_status():
    ctx = create_auto_approve_context(patterns={"todo": ["*"]})

    todos = [
        {
            "id": "t1",
            "content": "Bad status",
            "status": "blocked",
            "priority": "low",
        }
    ]

    result = await todowrite(todos, ctx)
    assert result.is_error
