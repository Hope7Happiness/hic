# OpenCode Builtin Tools Analysis

**Date:** January 26, 2026  
**Analyzed Repository:** `/Users/peppaking8/Desktop/coding/hic/external/opencode/`  
**Purpose:** Learn from OpenCode's tool architecture to improve HIC's builtin tools

---

## Executive Summary

OpenCode is a TypeScript-based AI coding assistant that implements a sophisticated tool system with 15+ builtin tools. Despite being in TypeScript, its architectural patterns and design decisions are highly valuable for improving HIC's Python-based tool system.

### Key Findings

1. **Permission-First Architecture:** Every tool operation requires explicit user permission through a unified `ctx.ask()` system
2. **Intelligent Output Management:** Automatic truncation with file spillover enables handling large outputs without context bloat
3. **Resilient Edit Tool:** Uses 9 different matching strategies to handle LLM-generated imperfect strings
4. **Structured Tool Returns:** Separate `title`, `metadata`, `output`, and `attachments` fields optimize for both UI and LLM consumption
5. **Real-time Feedback:** Metadata streaming provides progress updates during long-running operations
6. **Security by Default:** Path validation, command parsing, and dangerous operation detection protect users

### Architecture Comparison

| Aspect | HIC (Current) | OpenCode | Recommendation |
|--------|---------------|----------|----------------|
| Tool Definition | Function-based | Class-based with `Tool.define()` | Adopt hybrid approach |
| Permissions | None | Required for all operations | **Critical to add** |
| Output Truncation | Manual | Automatic with spillover | **Must implement** |
| Error Handling | Basic | Multi-strategy with fallbacks | Enhance significantly |
| Context | Minimal | Rich (abort, metadata, messages) | Expand context object |
| Return Format | Simple string | Structured (title/metadata/output) | Adopt structured format |
| LSP Integration | None | Full integration | Consider for v2 |
| User Interaction | None | `question` tool | **High priority** |

---

## Tool-by-Tool Analysis

### 1. `bash.ts` - Shell Command Execution

**File:** `packages/opencode/src/tool/bash.ts` (259 lines)

#### Features

- **Command Parsing:** Uses tree-sitter to parse shell commands and extract file paths
- **Permission System:** Requests approval before execution, with auto-approve patterns
- **Timeout Support:** Configurable timeout (default 2 minutes)
- **Process Management:** Proper process tree killing on abort/timeout
- **Output Streaming:** Real-time metadata updates as output is produced
- **Security Checks:**
  - Detects dangerous commands (rm -rf, chmod, etc.)
  - Warns when accessing external directories
  - Path validation

#### Key Implementation Details

```typescript
// Permission request with pattern matching
await ctx.ask({
  permission: "bash",
  patterns: [command],
  always: ["*"],  // User can set auto-approve patterns
  metadata: {
    command,
    cwd,
    timeout,
    external_directories: externalDirs
  }
})

// Process spawning with proper cleanup
const proc = spawn(command, {
  shell,
  cwd,
  stdio: ["ignore", "pipe", "pipe"],
  detached: true  // For process group killing
})

// Real-time output streaming
proc.stdout?.on("data", (chunk) => {
  output += chunk.toString()
  ctx.metadata({ metadata: { output: truncated } })
})
```

#### Python Adaptation Considerations

- **Tree-sitter:** Available in Python via `tree-sitter` package
- **Process Management:** Use `subprocess.Popen()` with `process.pid` for cleanup
- **Async Streaming:** Use `asyncio.create_subprocess_exec()` for non-blocking I/O
- **Security:** Implement command validation before execution

**Priority:** High (enhance existing `restricted_bash`)

---

### 2. `edit.ts` - Advanced String Replacement

**File:** `packages/opencode/src/tool/edit.ts` (646 lines!)

#### Why So Complex?

LLMs frequently produce `oldString` values with minor formatting errors:
- Wrong indentation (spaces vs tabs)
- Extra/missing whitespace
- Escaped characters vs literal characters
- Line endings variations

OpenCode solves this with **9 different replacement strategies** tried in sequence.

#### The 9 Replacement Strategies

1. **SimpleReplacer** - Exact string match
   ```typescript
   if (content.includes(oldString)) {
     return content.replace(oldString, newString)
   }
   ```

2. **LineTrimmedReplacer** - Trims each line before matching
   ```typescript
   // "  hello\n  world" matches "hello\nworld"
   ```

3. **BlockAnchorReplacer** - Matches by first and last lines
   ```typescript
   // Find blocks where first/last line match, ignore middle
   ```

4. **WhitespaceNormalizedReplacer** - Normalizes all whitespace
   ```typescript
   // "hello    world" matches "hello world"
   ```

5. **IndentationFlexibleReplacer** - Ignores indentation differences
   ```typescript
   // "  def foo():" matches "    def foo():"
   ```

6. **EscapeNormalizedReplacer** - Normalizes escape sequences
   ```typescript
   // "\n" matches actual newline
   ```

7. **TrimmedBoundaryReplacer** - Trims boundaries only
   ```typescript
   // "  hello  " matches "hello"
   ```

8. **ContextAwareReplacer** - Uses surrounding context
   ```typescript
   // Matches based on lines before/after
   ```

9. **MultiOccurrenceReplacer** - Finds all occurrences
   ```typescript
   // When string appears multiple times, require more context
   ```

#### Fuzzy Matching with Levenshtein Distance

```typescript
const similarity = 1 - (levenshteinDistance(a, b) / Math.max(a.length, b.length))
if (similarity >= SIMILARITY_THRESHOLD) {
  // Accept the match
}
```

Thresholds:
- Normal: 0.8 similarity
- Strict: 0.9 similarity
- Prevent false positives on very different strings

#### Additional Features

- **File Locking:** Prevents race conditions on concurrent edits
- **LSP Integration:** Runs diagnostics after edit to detect errors
- **Diff Generation:** Creates unified diff for UI display
- **Metadata Rich:** Returns line numbers, similarity scores, strategy used
- **replaceAll Option:** Replace all occurrences vs single occurrence

#### Example Tool Call

```json
{
  "tool": "edit",
  "parameters": {
    "filePath": "/path/to/file.py",
    "oldString": "def old_function():\n    pass",
    "newString": "def new_function():\n    print('updated')",
    "replaceAll": false
  }
}
```

#### Python Adaptation

```python
from typing import Protocol, Optional
import difflib
from Levenshtein import distance as levenshtein_distance

class Replacer(Protocol):
    def try_replace(
        self, 
        content: str, 
        old: str, 
        new: str
    ) -> Optional[str]:
        """Returns new content if replacement succeeded, None otherwise."""
        ...

class SimpleReplacer:
    def try_replace(self, content: str, old: str, new: str) -> Optional[str]:
        if old in content:
            count = content.count(old)
            if count == 1:
                return content.replace(old, new)
            else:
                # Multiple occurrences - need more context
                return None
        return None

class LineTrimmedReplacer:
    def try_replace(self, content: str, old: str, new: str) -> Optional[str]:
        # Trim each line before comparing
        content_lines = [line.strip() for line in content.split('\n')]
        old_lines = [line.strip() for line in old.split('\n')]
        # ... matching logic
```

**Priority:** **CRITICAL** - This is the most important tool to implement well

---

### 3. `read.ts` - File Reading with Pagination

**File:** `packages/opencode/src/tool/read.ts` (212 lines)

#### Features

- **Pagination:** `offset` and `limit` parameters for reading large files
- **Line Numbering:** Format: `00001| content` (cat -n style)
- **Binary Detection:** Refuses to read binary files, suggests alternatives
- **Image/PDF Support:** Returns as attachments for LLM consumption
- **Similar File Suggestions:** On file not found, suggests similar filenames
- **Instruction Files:** Automatically loads `.context.md` or similar
- **LSP Warmup:** Opens file in LSP for faster diagnostics

#### Key Implementation

```typescript
// Line numbering with padding
const lineNumWidth = String(endLine).length
lines.forEach((line, idx) => {
  const lineNum = String(startLine + idx).padStart(lineNumWidth, '0')
  output += `${lineNum}| ${line}\n`
})

// Truncation notice
if (totalLines > limit) {
  output += `\n... (${totalLines - limit} more lines)\n`
  output += `Use offset=${offset + limit} to read more`
}
```

#### Return Format

```typescript
return {
  title: `Read ${filePath}`,
  metadata: {
    file_path: filePath,
    lines_read: linesRead,
    total_lines: totalLines,
    offset,
    limit,
    is_truncated: totalLines > limit
  },
  output: output,  // For LLM
  attachments: imageData ? [imageData] : undefined
}
```

#### Python Adaptation

- **Built-in:** Python's `open()` with `readlines()` handles this easily
- **Binary Detection:** Use `mimetypes` or `file` command
- **Pagination:** Simple slice: `lines[offset:offset+limit]`
- **Image Support:** Use `base64` encoding

**Priority:** Medium (basic version already exists)

---

### 4. `write.ts` - File Writing/Creation

**File:** `packages/opencode/src/tool/write.ts` (81 lines)

#### Features

- **Create or Overwrite:** Handles both new files and updates
- **Directory Creation:** Automatically creates parent directories
- **Diff Generation:** Shows unified diff of changes
- **LSP Diagnostics:** Runs error checking after write
- **Cross-file Impact:** Shows errors in other files affected by the change
- **Metadata Rich:** File size, line count, errors

#### Permission Request

```typescript
await ctx.ask({
  permission: "write",
  patterns: [filePath],
  always: [],
  metadata: {
    file_path: filePath,
    exists: fileExists,
    size_bytes: content.length,
    line_count: content.split('\n').length
  }
})
```

#### LSP Integration

```typescript
// After writing file
const diagnostics = await lsp.getDiagnostics(filePath)
const errors = diagnostics.filter(d => d.severity === 'error')

if (errors.length > 0) {
  metadata.errors = errors
  output += '\n\n⚠️ Errors detected:\n'
  errors.forEach(err => {
    output += `  Line ${err.line}: ${err.message}\n`
  })
}
```

#### Python Adaptation

```python
import os
from pathlib import Path
import difflib

async def write_file(file_path: str, content: str, ctx: Context) -> ToolResult:
    path = Path(file_path)
    exists = path.exists()
    
    # Read old content for diff
    old_content = path.read_text() if exists else ""
    
    # Request permission
    await ctx.ask({
        "permission": "write",
        "patterns": [file_path],
        "metadata": {
            "exists": exists,
            "size_bytes": len(content)
        }
    })
    
    # Create parent dirs
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file
    path.write_text(content)
    
    # Generate diff
    diff = list(difflib.unified_diff(
        old_content.splitlines(),
        content.splitlines(),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm=""
    ))
    
    return {
        "title": f"{'Updated' if exists else 'Created'} {file_path}",
        "metadata": {"exists": exists, "size": len(content)},
        "output": "\n".join(diff)
    }
```

**Priority:** High (simple and very useful)

---

### 5. `glob.ts` - File Pattern Matching

**File:** `packages/opencode/src/tool/glob.ts` (78 lines)

#### Features

- **Ripgrep-based:** Uses `rg --files` for performance
- **Modification Time Sorting:** Most recent files first
- **Result Truncation:** Max 100 results
- **Hidden Files:** Option to include/exclude
- **Gitignore Respect:** Honors `.gitignore` by default

#### Implementation

```typescript
const args = [
  '--files',
  '--glob', pattern,
  '--sort', 'modified',
  '--max-count', '100'
]

if (!includeHidden) {
  args.push('--hidden')
}

const { stdout } = await execAsync(`rg ${args.join(' ')}`, { cwd })
const files = stdout.trim().split('\n').filter(Boolean)
```

#### Python Adaptation

```python
import subprocess
from pathlib import Path

def glob_files(pattern: str, path: str = ".", max_results: int = 100) -> list[str]:
    """Find files matching glob pattern using ripgrep."""
    try:
        result = subprocess.run(
            ["rg", "--files", "--glob", pattern, "--max-count", str(max_results)],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        files = result.stdout.strip().split('\n')
        files = [f for f in files if f]
        
        # Sort by modification time (most recent first)
        files.sort(key=lambda f: Path(path) / f).stat().st_mtime, reverse=True)
        
        return files[:max_results]
    except FileNotFoundError:
        # Fallback to Python's glob if ripgrep not available
        import glob as pyglob
        return list(pyglob.glob(pattern, recursive=True))[:max_results]
```

**Priority:** Medium (useful for file discovery)

---

### 6. `grep.ts` - Content Search

**File:** `packages/opencode/src/tool/grep.ts` (155 lines)

#### Features

- **Ripgrep-based:** Fast content search with regex support
- **File Filtering:** Include/exclude patterns
- **Context Lines:** Show N lines before/after match
- **Result Truncation:** Max results to prevent context bloat
- **Match Highlighting:** Uses ANSI codes for terminal display
- **Line Numbers:** Shows exact line of match

#### Implementation

```typescript
const args = [
  '--json',  // Structured output
  '--line-number',
  '--column',
  '--context', String(contextLines),
  '--max-count', String(maxResults),
  '--regexp', pattern
]

if (include) {
  args.push('--glob', include)
}

const { stdout } = await execAsync(`rg ${args.join(' ')}`, { cwd })

// Parse JSON output
const matches = stdout.split('\n')
  .filter(Boolean)
  .map(line => JSON.parse(line))
  .filter(m => m.type === 'match')
```

#### Return Format

```typescript
return {
  title: `Found ${matches.length} matches for "${pattern}"`,
  metadata: {
    pattern,
    match_count: matches.length,
    file_count: uniqueFiles.length,
    is_truncated: matches.length >= maxResults
  },
  output: formattedMatches
}
```

#### Python Adaptation

```python
import subprocess
import json

def grep_content(
    pattern: str, 
    path: str = ".", 
    include: str = None,
    max_results: int = 100
) -> dict:
    """Search file contents using ripgrep."""
    args = [
        "rg",
        "--json",
        "--line-number",
        "--column",
        "--max-count", str(max_results),
        pattern
    ]
    
    if include:
        args.extend(["--glob", include])
    
    result = subprocess.run(
        args,
        cwd=path,
        capture_output=True,
        text=True,
        timeout=30
    )
    
    matches = []
    for line in result.stdout.strip().split('\n'):
        if line:
            data = json.loads(line)
            if data.get('type') == 'match':
                matches.append({
                    'file': data['data']['path']['text'],
                    'line': data['data']['line_number'],
                    'column': data['data']['submatches'][0]['start'],
                    'text': data['data']['lines']['text']
                })
    
    return {
        "title": f"Found {len(matches)} matches",
        "metadata": {"count": len(matches)},
        "output": format_matches(matches)
    }
```

**Priority:** High (essential for code exploration)

---

### 7. `todo.ts` - Task Management

**File:** `packages/opencode/src/tool/todo.ts` (54 lines)

#### Features

- **Session-scoped:** Each conversation has its own todo list
- **Structured Data:** 
  - `id` - Unique identifier
  - `content` - Task description
  - `status` - `pending`, `in_progress`, `completed`, `cancelled`
  - `priority` - `high`, `medium`, `low`
- **Two Operations:**
  - `todowrite` - Create/update todo list
  - `todoread` - Read current todo list

#### Data Structure

```typescript
interface Todo {
  id: string
  content: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  priority: 'high' | 'medium' | 'low'
}

interface TodoList {
  session_id: string
  todos: Todo[]
  updated_at: string
}
```

#### Storage

```typescript
// Stored in session metadata
const todoList = ctx.getSessionMetadata('todos') || { todos: [] }

// Updated via todowrite
await ctx.setSessionMetadata('todos', {
  todos: updatedTodos,
  updated_at: new Date().toISOString()
})
```

#### Python Adaptation

```python
from dataclasses import dataclass
from typing import Literal
from datetime import datetime

@dataclass
class Todo:
    id: str
    content: str
    status: Literal['pending', 'in_progress', 'completed', 'cancelled']
    priority: Literal['high', 'medium', 'low']

@dataclass
class TodoList:
    session_id: str
    todos: list[Todo]
    updated_at: str

# Store in context
class Context:
    def __init__(self):
        self._metadata = {}
    
    def get_todos(self) -> TodoList:
        return self._metadata.get('todos', TodoList(
            session_id=self.session_id,
            todos=[],
            updated_at=datetime.now().isoformat()
        ))
    
    def set_todos(self, todos: list[Todo]):
        self._metadata['todos'] = TodoList(
            session_id=self.session_id,
            todos=todos,
            updated_at=datetime.now().isoformat()
        )
```

**Priority:** Medium (nice for task tracking, improves agent reliability)

---

### 8. `webfetch.ts` - HTTP Content Fetching

**File:** `packages/opencode/src/tool/webfetch.ts` (189 lines)

#### Features

- **Format Conversion:**
  - `markdown` - HTML → Markdown (default)
  - `text` - Extract plain text
  - `html` - Raw HTML
- **Smart User-Agent:** Avoids bot detection (Cloudflare, etc.)
- **Content-Type Negotiation:** Handles various response types
- **Size Limits:** Max 5MB to prevent memory issues
- **Timeout Support:** Configurable (default 30s)
- **Error Handling:** Network errors, redirects, rate limits

#### HTML to Markdown Conversion

```typescript
import TurndownService from 'turndown'

const turndown = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced',
  bulletListMarker: '-'
})

// Custom rules for better conversion
turndown.addRule('removeScripts', {
  filter: ['script', 'style', 'nav', 'footer'],
  replacement: () => ''
})

const markdown = turndown.turndown(html)
```

#### User-Agent Handling

```typescript
const USER_AGENTS = {
  default: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
  mobile: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
  bot: 'OpenCodeBot/1.0'
}

const response = await fetch(url, {
  headers: {
    'User-Agent': USER_AGENTS.default,
    'Accept': 'text/html,application/json,*/*'
  },
  timeout: 30000,
  redirect: 'follow'
})
```

#### Python Adaptation

```python
import requests
from bs4 import BeautifulSoup
import html2text

def webfetch(
    url: str, 
    format: str = "markdown",
    timeout: int = 30
) -> dict:
    """Fetch web content and convert to specified format."""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/json,*/*'
    }
    
    response = requests.get(
        url, 
        headers=headers, 
        timeout=timeout,
        allow_redirects=True
    )
    response.raise_for_status()
    
    # Check size
    if len(response.content) > 5 * 1024 * 1024:  # 5MB
        raise ValueError("Response too large (>5MB)")
    
    content_type = response.headers.get('content-type', '')
    
    if format == "markdown" and 'html' in content_type:
        # Convert HTML to Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        output = h.handle(response.text)
    elif format == "text":
        # Extract text only
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        output = soup.get_text(separator='\n', strip=True)
    else:
        output = response.text
    
    return {
        "title": f"Fetched {url}",
        "metadata": {
            "url": url,
            "status_code": response.status_code,
            "content_type": content_type,
            "size_bytes": len(response.content)
        },
        "output": output
    }
```

**Dependencies:**
```bash
pip install requests beautifulsoup4 html2text
```

**Priority:** Medium (useful for docs/web research)

---

### 9. `question.ts` - User Interaction

**File:** `packages/opencode/src/tool/question.ts` (34 lines)

#### Purpose

Allows agent to ask user clarifying questions during execution.

#### Features

- **Multi-question Support:** Ask multiple questions at once
- **Structured Options:** Provide choices with descriptions
- **Custom Answers:** Allow free-form text input
- **Multiple Selection:** User can select multiple options
- **Blocking:** Tool waits for user response before continuing

#### Data Structure

```typescript
interface Question {
  header: string  // Short label (max 30 chars)
  question: string  // Full question text
  options: Array<{
    label: string  // Display text (1-5 words)
    description: string  // Explanation of choice
  }>
  multiple?: boolean  // Allow multiple selections
}
```

#### Example Usage

```typescript
const answers = await question({
  questions: [{
    header: "API Choice",
    question: "Which API should I use for user authentication?",
    options: [
      {
        label: "OAuth 2.0",
        description: "Industry standard, supports third-party providers"
      },
      {
        label: "JWT",
        description: "Stateless, good for microservices"
      },
      {
        label: "Session-based",
        description: "Traditional, server-side sessions"
      }
    ],
    multiple: false
  }]
})

// answers = [{ question_index: 0, selected: ["OAuth 2.0"] }]
```

#### Python Adaptation

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class QuestionOption:
    label: str
    description: str

@dataclass
class Question:
    header: str
    question: str
    options: list[QuestionOption]
    multiple: bool = False

@dataclass
class Answer:
    question_index: int
    selected: list[str]

async def ask_question(questions: list[Question], ctx: Context) -> list[Answer]:
    """Ask user questions and wait for answers."""
    
    # Send question request to UI
    await ctx.ask({
        "permission": "question",
        "patterns": [],
        "metadata": {
            "questions": [q.__dict__ for q in questions]
        }
    })
    
    # Block until user responds
    answers = await ctx.wait_for_user_input()
    
    return [Answer(**a) for a in answers]
```

**Priority:** **HIGH** - Critical for clarification and user preferences

---

### 10. Other Tools (Brief Overview)

#### `ls.ts` - Directory Listing
- List files and folders with metadata
- File sizes, modification times, permissions
- Tree view option
- Hidden file support

**Priority:** Low (basic functionality, `glob` covers most use cases)

---

#### `lsp.ts` - Language Server Protocol Integration
- Real-time error detection
- Code completion support
- Go-to-definition
- Find references
- Rename refactoring

**Priority:** Low (advanced feature, complex to implement)

---

#### `apply_patch.ts` - Patch Application
- Apply unified diffs to files
- Handles context mismatches
- Fuzzy patch matching
- Fallback strategies

**Priority:** Low (edit tool covers most needs)

---

#### `codesearch.ts` / `websearch.ts` - External Search
- Integration with external search APIs
- Code-specific search (GitHub, StackOverflow)
- Web search for documentation

**Priority:** Low (nice-to-have, not critical)

---

#### `batch.ts` / `plan.ts` / `task.ts` - Agent Orchestration
- Parallel tool execution
- Sub-agent spawning
- Task decomposition
- Progress tracking

**Priority:** Low (meta-features, implement after core tools solid)

---

## Architecture Patterns

### 1. Tool Definition Pattern

OpenCode uses a factory pattern with `Tool.define()`:

```typescript
export const BashTool = Tool.define("bash", async () => {
  return {
    description: DESCRIPTION,  // Loaded from bash.txt
    parameters: z.object({
      command: z.string().describe("Shell command to execute"),
      workdir: z.string().optional().describe("Working directory"),
      timeout: z.number().optional().describe("Timeout in milliseconds")
    }),
    async execute(params, ctx) {
      // Implementation
      return {
        title: "Executed command",
        metadata: { /* structured data */ },
        output: "..." // text for LLM
      }
    }
  }
})
```

**Benefits:**
- Lazy loading of tool implementations
- Clear separation of description and implementation
- Type-safe parameters via Zod schemas
- Consistent interface across all tools

**HIC Adaptation:**

```python
from typing import Protocol, Any
from pydantic import BaseModel

class ToolParameters(BaseModel):
    """Base class for tool parameters."""
    pass

class ToolResult:
    def __init__(
        self, 
        title: str, 
        output: str, 
        metadata: dict = None,
        attachments: list = None
    ):
        self.title = title
        self.output = output
        self.metadata = metadata or {}
        self.attachments = attachments or []

class Tool:
    def __init__(
        self, 
        name: str, 
        description: str,
        parameters_schema: type[ToolParameters]
    ):
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
    
    async def execute(
        self, 
        params: ToolParameters, 
        ctx: 'Context'
    ) -> ToolResult:
        """Execute the tool and return result."""
        raise NotImplementedError
    
    @classmethod
    def define(
        cls, 
        name: str, 
        description: str,
        parameters_schema: type[ToolParameters]
    ):
        """Factory method for creating tools."""
        def decorator(execute_func):
            tool = cls(name, description, parameters_schema)
            tool.execute = execute_func
            return tool
        return decorator

# Usage
class BashParams(ToolParameters):
    command: str
    workdir: str = "."
    timeout: int = 120000

@Tool.define(
    "bash",
    "Execute shell commands",
    BashParams
)
async def bash_tool(params: BashParams, ctx: Context) -> ToolResult:
    # Implementation
    return ToolResult(
        title=f"Executed: {params.command}",
        output=stdout,
        metadata={"exit_code": 0}
    )
```

---

### 2. Context and Permissions

Every tool receives a `Context` object with rich information:

```typescript
interface Context {
  // Identity
  sessionID: string
  messageID: string
  agent: string
  callID?: string
  
  // Cancellation
  abort: AbortSignal
  
  // Communication
  messages: MessageV2.WithParts[]  // Full conversation history
  metadata(input: any): void  // Stream metadata updates
  ask(request: PermissionRequest): Promise<void>  // Request permission
  
  // Session data
  getSessionMetadata(key: string): any
  setSessionMetadata(key: string, value: any): void
}
```

#### Permission Request Flow

```typescript
// Tool requests permission
await ctx.ask({
  permission: "bash",  // Permission type
  patterns: [command],  // What's being accessed
  always: ["*"],  // Auto-approve patterns (user config)
  metadata: {
    command,
    cwd,
    external_directories: ["/etc", "/usr"]
  }
})

// UI shows permission dialog to user
// User approves/denies
// If denied, tool throws PermissionDeniedError
```

#### HIC Adaptation

```python
from dataclasses import dataclass
from typing import Any, Callable
import asyncio

@dataclass
class PermissionRequest:
    permission: str  # "bash", "write", "read", etc.
    patterns: list[str]  # File paths, commands, URLs
    always: list[str]  # Auto-approve patterns
    metadata: dict[str, Any]

class Context:
    def __init__(
        self, 
        session_id: str,
        message_id: str,
        messages: list,
        permission_handler: Callable
    ):
        self.session_id = session_id
        self.message_id = message_id
        self.messages = messages
        self._permission_handler = permission_handler
        self._metadata = {}
        self._abort_event = asyncio.Event()
    
    async def ask(self, request: PermissionRequest) -> None:
        """Request permission from user."""
        approved = await self._permission_handler(request)
        if not approved:
            raise PermissionDeniedError(
                f"Permission denied: {request.permission}"
            )
    
    def metadata(self, data: dict) -> None:
        """Stream metadata update to UI."""
        self._metadata.update(data)
        # Send to UI via event bus
    
    def get_session_metadata(self, key: str, default=None):
        return self._metadata.get(key, default)
    
    def set_session_metadata(self, key: str, value: Any):
        self._metadata[key] = value
    
    def abort(self):
        """Signal abortion to running tools."""
        self._abort_event.set()
    
    @property
    def is_aborted(self) -> bool:
        return self._abort_event.is_set()
```

---

### 3. Output Management and Truncation

OpenCode implements automatic output truncation to prevent context bloat:

```typescript
const MAX_LINES = 2000
const MAX_BYTES = 51200  // 50KB

function truncateOutput(output: string, ctx: Context): string {
  const lines = output.split('\n')
  const bytes = Buffer.byteLength(output, 'utf-8')
  
  if (lines.length <= MAX_LINES && bytes <= MAX_BYTES) {
    return output  // No truncation needed
  }
  
  // Write full output to temporary file
  const tempFile = `/tmp/output_${ctx.callID}.txt`
  fs.writeFileSync(tempFile, output)
  
  // Return truncated output with instructions
  const truncated = lines.slice(0, MAX_LINES).join('\n')
  
  return `${truncated}\n\n` +
    `[Output truncated: ${lines.length} total lines, ${bytes} bytes]\n` +
    `Full output written to: ${tempFile}\n` +
    `Use the 'read' tool with offset/limit to read specific sections.`
}
```

**Benefits:**
- Prevents overwhelming LLM context
- Preserves full data for later access
- Gives agent guidance on how to access more
- Automatic and transparent

**HIC Adaptation:**

```python
import tempfile
from pathlib import Path

class OutputTruncator:
    MAX_LINES = 2000
    MAX_BYTES = 51200  # 50KB
    
    def __init__(self, temp_dir: str = None):
        self.temp_dir = Path(temp_dir or tempfile.gettempdir())
    
    def truncate(self, output: str, call_id: str) -> tuple[str, dict]:
        """
        Truncate output if needed.
        
        Returns:
            (truncated_output, metadata)
        """
        lines = output.split('\n')
        byte_size = len(output.encode('utf-8'))
        
        metadata = {
            "total_lines": len(lines),
            "total_bytes": byte_size,
            "is_truncated": False
        }
        
        if len(lines) <= self.MAX_LINES and byte_size <= self.MAX_BYTES:
            return output, metadata
        
        # Write full output to file
        temp_file = self.temp_dir / f"output_{call_id}.txt"
        temp_file.write_text(output)
        
        # Truncate
        truncated_lines = lines[:self.MAX_LINES]
        truncated = '\n'.join(truncated_lines)
        
        footer = (
            f"\n\n[Output truncated: {len(lines)} total lines, {byte_size} bytes]\n"
            f"Full output written to: {temp_file}\n"
            f"Use the 'read' tool with offset={self.MAX_LINES} to read more."
        )
        
        metadata.update({
            "is_truncated": True,
            "truncated_at_line": self.MAX_LINES,
            "full_output_file": str(temp_file)
        })
        
        return truncated + footer, metadata
```

---

### 4. Error Handling and Resilience

OpenCode tools implement multi-layered error handling:

#### Layer 1: Input Validation

```typescript
// Validate parameters before execution
if (!fs.existsSync(filePath)) {
  // Suggest similar files
  const files = await globFiles("**/*", cwd)
  const similar = files
    .map(f => ({ file: f, distance: levenshtein(filePath, f) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 5)
  
  throw new Error(
    `File not found: ${filePath}\n` +
    `Did you mean one of these?\n` +
    similar.map(s => `  - ${s.file}`).join('\n')
  )
}
```

#### Layer 2: Operation Timeout

```typescript
const timeoutPromise = new Promise((_, reject) => {
  setTimeout(() => reject(new Error('Operation timeout')), timeout)
})

const result = await Promise.race([
  actualOperation(),
  timeoutPromise
])
```

#### Layer 3: Graceful Degradation

```typescript
// Try primary strategy
try {
  return await primaryStrategy()
} catch (error) {
  // Fall back to secondary strategy
  try {
    return await secondaryStrategy()
  } catch (error2) {
    // Fall back to manual mode
    return await manualStrategy()
  }
}
```

#### Layer 4: User-Friendly Error Messages

```typescript
try {
  await dangerousOperation()
} catch (error) {
  // Transform technical error into actionable message
  if (error.code === 'EACCES') {
    throw new Error(
      `Permission denied: Cannot access ${path}\n` +
      `Try running with sudo, or check file permissions:\n` +
      `  chmod +r ${path}`
    )
  } else if (error.code === 'ENOENT') {
    throw new Error(
      `File not found: ${path}\n` +
      `Make sure the file exists and the path is correct.`
    )
  } else {
    throw new Error(
      `Operation failed: ${error.message}\n` +
      `If this persists, please report an issue.`
    )
  }
}
```

**HIC Adaptation:**

```python
import errno
from typing import Optional
from Levenshtein import distance

class ToolError(Exception):
    """Base class for tool errors."""
    def __init__(self, message: str, suggestions: list[str] = None):
        super().__init__(message)
        self.suggestions = suggestions or []

def suggest_similar_files(target: str, candidates: list[str], max_suggestions: int = 5) -> list[str]:
    """Find files similar to target using Levenshtein distance."""
    similarities = [
        (file, distance(target, file))
        for file in candidates
    ]
    similarities.sort(key=lambda x: x[1])
    return [file for file, _ in similarities[:max_suggestions]]

async def read_file_with_fallback(file_path: str) -> str:
    """Read file with error handling and suggestions."""
    try:
        return Path(file_path).read_text()
    except FileNotFoundError:
        # Find similar files
        all_files = glob_files("**/*")
        similar = suggest_similar_files(file_path, all_files)
        
        suggestion_text = "\n".join(f"  - {f}" for f in similar)
        raise ToolError(
            f"File not found: {file_path}\n"
            f"Did you mean one of these?\n{suggestion_text}",
            suggestions=similar
        )
    except PermissionError:
        raise ToolError(
            f"Permission denied: {file_path}\n"
            f"Try checking file permissions:\n"
            f"  chmod +r {file_path}"
        )
    except UnicodeDecodeError:
        raise ToolError(
            f"Cannot read file: {file_path}\n"
            f"File appears to be binary. Try using a different tool."
        )
```

---

### 5. Structured Return Format

All OpenCode tools return a consistent structure:

```typescript
interface ToolResult {
  // For UI display (short, human-readable)
  title: string
  
  // For UI and tracking (structured data)
  metadata: Record<string, any>
  
  // For LLM consumption (detailed text)
  output: string
  
  // For special data (images, files, etc.)
  attachments?: Array<{
    type: 'image' | 'file' | 'data'
    content: string | Buffer
    filename?: string
    mime_type?: string
  }>
}
```

**Example:**

```typescript
return {
  title: "Executed: npm install",
  metadata: {
    command: "npm install",
    exit_code: 0,
    duration_ms: 5432,
    packages_installed: 247
  },
  output: "added 247 packages in 5.432s\n\n" +
    "Dependencies:\n" +
    "  react@18.2.0\n" +
    "  typescript@5.0.0\n" +
    "  ...",
  attachments: []
}
```

**Benefits:**
- UI can display title immediately
- Metadata enables filtering/sorting/analytics
- Output optimized for LLM understanding
- Attachments handle non-text data

**HIC Adaptation:**

```python
from dataclasses import dataclass, field
from typing import Any, Optional, Literal

@dataclass
class Attachment:
    type: Literal['image', 'file', 'data']
    content: bytes | str
    filename: Optional[str] = None
    mime_type: Optional[str] = None

@dataclass
class ToolResult:
    title: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "output": self.output,
            "metadata": self.metadata,
            "attachments": [
                {
                    "type": a.type,
                    "content": a.content,
                    "filename": a.filename,
                    "mime_type": a.mime_type
                }
                for a in self.attachments
            ]
        }
```

---

## Security and Safety

### 1. Permission System

**Implementation:**
- Every tool operation requires explicit permission
- Permissions are scoped: `bash`, `read`, `write`, `webfetch`, etc.
- Users can configure auto-approve patterns
- UI shows clear permission dialogs

**Example Flow:**
```
Agent: I need to read config.json
Tool: Requests permission via ctx.ask()
UI: Shows dialog: "Allow reading config.json?"
User: Approves
Tool: Proceeds with operation
```

**Auto-approve Example:**
```json
{
  "permissions": {
    "read": {
      "always": ["*.md", "*.txt", "package.json"]
    },
    "bash": {
      "always": ["npm install", "npm test", "git status"]
    }
  }
}
```

### 2. Path Validation

```typescript
function isPathSafe(filePath: string, cwd: string): boolean {
  const resolved = path.resolve(cwd, filePath)
  const relativePath = path.relative(cwd, resolved)
  
  // Check if path escapes project directory
  if (relativePath.startsWith('..')) {
    return false
  }
  
  // Check for absolute paths outside project
  if (path.isAbsolute(filePath) && !filePath.startsWith(cwd)) {
    return false
  }
  
  return true
}
```

### 3. Command Parsing

Uses tree-sitter to parse shell commands and detect:
- File operations
- External directory access
- Dangerous commands (rm -rf, etc.)
- Network operations

```typescript
import Parser from 'tree-sitter'
import Bash from 'tree-sitter-bash'

const parser = new Parser()
parser.setLanguage(Bash)

const tree = parser.parse(command)
const dangerousPatterns = [
  'rm -rf',
  'rm -r',
  'chmod 777',
  'sudo',
  'curl | bash'
]

for (const pattern of dangerousPatterns) {
  if (command.includes(pattern)) {
    // Warn user
  }
}
```

### 4. Timeout Protection

All operations have timeouts:
- Bash: 2 minutes default
- Webfetch: 30 seconds default
- File operations: 10 seconds default

```typescript
async function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  errorMsg: string
): Promise<T> {
  const timeout = new Promise<never>((_, reject) => {
    setTimeout(() => reject(new Error(errorMsg)), ms)
  })
  return Promise.race([promise, timeout])
}
```

### 5. Process Isolation

```typescript
// Spawn process in separate process group
const proc = spawn(command, {
  detached: true,  // Create new process group
  stdio: ['ignore', 'pipe', 'pipe']
})

// On abort, kill entire process tree
ctx.abort.addEventListener('abort', () => {
  if (proc.pid) {
    // Kill process group (negative PID)
    process.kill(-proc.pid, 'SIGTERM')
    
    // Force kill after 5 seconds
    setTimeout(() => {
      try {
        process.kill(-proc.pid, 'SIGKILL')
      } catch {}
    }, 5000)
  }
})
```

---

## Implementation Roadmap for HIC

### Phase 1: Foundation (Week 1-2)

**Goal:** Establish core architecture

1. **Context System**
   - Implement `Context` class with permission handling
   - Add session metadata storage
   - Implement abort signal mechanism

2. **Permission System**
   - Design permission request protocol
   - Implement permission handler interface
   - Create permission configuration system

3. **Structured Returns**
   - Define `ToolResult` dataclass
   - Implement `Attachment` support
   - Add metadata streaming

4. **Output Truncation**
   - Implement `OutputTruncator` class
   - Add temporary file management
   - Integrate with tool returns

**Deliverables:**
- [ ] `agent/context.py` - Context implementation
- [ ] `agent/permissions.py` - Permission system
- [ ] `agent/tool_result.py` - Structured results
- [ ] `agent/truncation.py` - Output management
- [ ] Tests for all above

---

### Phase 2: Core Tools (Week 3-4)

**Goal:** Implement essential tools with new architecture

1. **Enhanced Bash Tool**
   - Port tree-sitter command parsing
   - Add permission checks
   - Implement timeout and abort
   - Add output truncation

2. **Edit Tool** (Most Important!)
   - Implement 9 replacement strategies
   - Add Levenshtein fuzzy matching
   - File locking mechanism
   - Diff generation

3. **Write Tool**
   - Permission integration
   - Directory creation
   - Diff generation
   - Error handling

4. **Read Tool Enhancement**
   - Add pagination support
   - Binary file detection
   - Line numbering
   - Similar file suggestions

**Deliverables:**
- [ ] `agent/tools/bash.py` - Enhanced bash
- [ ] `agent/tools/edit.py` - Full edit implementation
- [ ] `agent/tools/write.py` - Write tool
- [ ] `agent/tools/read.py` - Enhanced read
- [ ] Tests for all tools

---

### Phase 3: Search & Discovery (Week 5)

**Goal:** Enable code exploration

1. **Grep Tool**
   - Ripgrep integration
   - Regex support
   - Result truncation
   - File filtering

2. **Glob Tool**
   - Pattern matching
   - Modification time sorting
   - Result limits

3. **Todo Tools**
   - todowrite implementation
   - todoread implementation
   - Session persistence

**Deliverables:**
- [ ] `agent/tools/grep.py`
- [ ] `agent/tools/glob.py`
- [ ] `agent/tools/todo.py`
- [ ] Tests

---

### Phase 4: User Interaction (Week 6)

**Goal:** Enable agent-user communication

1. **Question Tool**
   - Multi-question support
   - Structured options
   - Async user input
   - Integration with UI

2. **Webfetch Tool**
   - HTTP fetching
   - HTML to Markdown
   - Content extraction
   - Error handling

**Deliverables:**
- [ ] `agent/tools/question.py`
- [ ] `agent/tools/webfetch.py`
- [ ] UI integration for questions
- [ ] Tests

---

### Phase 5: Polish & Documentation (Week 7-8)

**Goal:** Production-ready tools

1. **Testing**
   - Integration tests
   - Security tests
   - Performance tests
   - Edge case coverage

2. **Documentation**
   - API reference
   - Usage examples
   - Security guidelines
   - Migration guide

3. **Examples**
   - Real-world usage examples
   - Best practices
   - Common patterns

4. **Performance**
   - Optimize hot paths
   - Add caching where appropriate
   - Profile and benchmark

**Deliverables:**
- [ ] Full test suite (>90% coverage)
- [ ] Complete documentation
- [ ] Example gallery
- [ ] Performance benchmarks

---

## Key Differences: HIC vs OpenCode

| Aspect | OpenCode (TypeScript) | HIC (Python) |
|--------|----------------------|--------------|
| **Language** | TypeScript/JavaScript | Python |
| **Async Model** | Promises, async/await | asyncio, async/await |
| **Schema Validation** | Zod | Pydantic |
| **Tree-sitter** | Native bindings | Python bindings |
| **Process Management** | child_process | subprocess, asyncio |
| **HTTP** | fetch API | requests, aiohttp |
| **Markdown** | Turndown | html2text, markdown2 |
| **LSP** | Built-in | python-lsp-server |
| **UI** | VS Code extension | CLI (for now) |
| **State Management** | Session-based | Context-based |

---

## Dependencies Required

### Core Dependencies

```bash
pip install \
  pydantic \          # Schema validation
  python-dotenv \     # Environment variables
  aiohttp \           # Async HTTP
  asyncio             # Async operations (built-in)
```

### Tool-Specific Dependencies

```bash
# Edit tool
pip install python-Levenshtein

# Webfetch tool
pip install \
  requests \
  beautifulsoup4 \
  lxml \
  html2text

# Bash tool
pip install \
  tree-sitter \
  tree-sitter-bash

# Search tools (ripgrep must be installed separately)
brew install ripgrep  # macOS
apt install ripgrep   # Ubuntu
```

### Optional Dependencies

```bash
# LSP integration
pip install python-lsp-server

# Testing
pip install \
  pytest \
  pytest-asyncio \
  pytest-cov \
  pytest-timeout
```

---

## Testing Strategy

### 1. Unit Tests

Test individual components in isolation:

```python
# test_edit_tool.py
import pytest
from agent.tools.edit import SimpleReplacer, LineTrimmedReplacer

def test_simple_replacer_exact_match():
    replacer = SimpleReplacer()
    content = "hello world\nfoo bar"
    old = "hello world"
    new = "goodbye world"
    
    result = replacer.try_replace(content, old, new)
    assert result == "goodbye world\nfoo bar"

def test_simple_replacer_multiple_matches():
    replacer = SimpleReplacer()
    content = "foo\nfoo\nfoo"
    old = "foo"
    new = "bar"
    
    # Should return None for multiple matches
    result = replacer.try_replace(content, old, new)
    assert result is None

def test_line_trimmed_replacer_whitespace():
    replacer = LineTrimmedReplacer()
    content = "  hello  \n  world  "
    old = "hello\nworld"
    new = "goodbye\nworld"
    
    result = replacer.try_replace(content, old, new)
    assert "goodbye" in result
```

### 2. Integration Tests

Test tools with real operations:

```python
# test_integration.py
import pytest
import tempfile
from pathlib import Path
from agent.tools.write import write_file
from agent.tools.read import read_file
from agent.tools.edit import edit_file
from agent.context import Context

@pytest.mark.asyncio
async def test_write_read_edit_workflow():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        ctx = create_test_context()
        
        # Write file
        result = await write_file(str(file_path), "def foo():\n    pass", ctx)
        assert result.title.startswith("Created")
        assert file_path.exists()
        
        # Read file
        result = await read_file(str(file_path), ctx)
        assert "def foo():" in result.output
        
        # Edit file
        result = await edit_file(
            str(file_path),
            "def foo():\n    pass",
            "def bar():\n    return 42",
            ctx
        )
        assert result.title.startswith("Edited")
        
        # Verify edit
        content = file_path.read_text()
        assert "def bar():" in content
        assert "return 42" in content
```

### 3. Security Tests

Test security features:

```python
# test_security.py
import pytest
from agent.tools.bash import bash_execute
from agent.permissions import PermissionDeniedError

@pytest.mark.asyncio
async def test_dangerous_command_requires_permission():
    ctx = create_test_context(auto_approve=False)
    
    with pytest.raises(PermissionDeniedError):
        await bash_execute("rm -rf /", ctx)

@pytest.mark.asyncio
async def test_external_directory_requires_permission():
    ctx = create_test_context(auto_approve=False)
    
    with pytest.raises(PermissionDeniedError):
        await read_file("/etc/passwd", ctx)

@pytest.mark.asyncio
async def test_path_traversal_blocked():
    ctx = create_test_context(cwd="/home/user/project")
    
    with pytest.raises(ValueError):
        await read_file("../../etc/passwd", ctx)
```

### 4. Performance Tests

Test performance characteristics:

```python
# test_performance.py
import pytest
import time
from agent.tools.grep import grep_files

@pytest.mark.slow
def test_grep_large_codebase():
    """Test grep performance on large codebase."""
    start = time.time()
    result = grep_files("TODO", path="/large/codebase")
    duration = time.time() - start
    
    assert duration < 5.0  # Should complete in < 5 seconds
    assert len(result.metadata["matches"]) > 0

@pytest.mark.slow
def test_output_truncation_performance():
    """Test truncation doesn't slow down significantly."""
    large_output = "x" * 10_000_000  # 10MB
    
    start = time.time()
    truncated, metadata = truncator.truncate(large_output, "test")
    duration = time.time() - start
    
    assert duration < 1.0  # Should be fast
    assert metadata["is_truncated"]
```

---

## Migration Path for Existing Code

### Step 1: Update Tool Signatures

```python
# Before
def restricted_bash(command: str, working_dir: str = ".") -> str:
    # ...
    return output

# After
async def restricted_bash(
    command: str, 
    working_dir: str = ".",
    ctx: Context = None
) -> ToolResult:
    # Request permission
    if ctx:
        await ctx.ask(PermissionRequest(
            permission="bash",
            patterns=[command],
            always=[],
            metadata={"command": command, "cwd": working_dir}
        ))
    
    # Execute command
    output = subprocess.run(...)
    
    # Return structured result
    return ToolResult(
        title=f"Executed: {command}",
        output=output,
        metadata={"exit_code": 0}
    )
```

### Step 2: Update Agent Integration

```python
# Before
observation = tool.execute(**params)
llm_output = await self.llm.chat(
    f"[TOOL RESULT from {tool.name}]\n{observation}"
)

# After
result = await tool.execute(params, ctx)

# Truncate if needed
truncated_output, metadata = truncator.truncate(
    result.output, 
    ctx.call_id
)

# Stream metadata to UI
ctx.metadata({
    "tool": tool.name,
    "result": result.metadata
})

# Send to LLM
llm_output = await self.llm.chat(
    f"[TOOL RESULT from {tool.name}]\n{result.title}\n\n{truncated_output}"
)
```

### Step 3: Update Examples

Update all examples in `examples/` to use new tool format.

---

## Recommendations

### Critical (Implement First)

1. **Edit Tool with Multiple Strategies**
   - This is the most important improvement
   - LLMs constantly produce imperfect strings
   - Will dramatically improve reliability

2. **Permission System**
   - Essential for safety
   - Builds user trust
   - Prevents accidents

3. **Output Truncation**
   - Critical for handling large outputs
   - Prevents context overflow
   - Improves performance

4. **Question Tool**
   - Enables clarification
   - Reduces errors from assumptions
   - Improves user experience

### High Priority

5. **Enhanced Bash Tool**
   - Tree-sitter parsing
   - Better error messages
   - Timeout and abort

6. **Write Tool with Diff**
   - Clear change visualization
   - Undo capability
   - Error detection

7. **Grep/Glob Tools**
   - Essential for code exploration
   - Fast searching
   - Pattern matching

### Medium Priority

8. **Todo Tools**
   - Improves agent reliability
   - Helps with complex tasks
   - Good for debugging

9. **Webfetch Tool**
   - Useful for documentation
   - Research capability
   - API exploration

### Low Priority (Future)

10. **LSP Integration**
    - Advanced feature
    - Requires significant work
    - Provides real-time errors

11. **Apply Patch Tool**
    - Niche use case
    - Edit tool covers most needs

12. **Batch/Plan/Task Tools**
    - Meta-features
    - Implement after core is solid

---

## Common Pitfalls to Avoid

### 1. **Not Handling Large Outputs**

**Problem:** Agent returns 10,000 lines of output, blows up context window.

**Solution:** Implement automatic truncation from day 1.

### 2. **Ignoring Edge Cases in Edit Tool**

**Problem:** Edit fails 30% of the time due to whitespace differences.

**Solution:** Implement multiple replacement strategies.

### 3. **No Permission System**

**Problem:** Agent accidentally deletes files, runs dangerous commands.

**Solution:** Require explicit permission for all operations.

### 4. **Poor Error Messages**

**Problem:** "File not found" with no additional help.

**Solution:** Suggest similar files, provide actionable steps.

### 5. **Blocking Operations**

**Problem:** Tool blocks entire agent while waiting for command.

**Solution:** Use async/await throughout, implement timeouts.

### 6. **No Abort Mechanism**

**Problem:** User can't cancel long-running operation.

**Solution:** Implement abort signals, check regularly.

### 7. **Inconsistent Return Format**

**Problem:** Some tools return strings, others return dicts.

**Solution:** Use structured `ToolResult` everywhere.

### 8. **No User Interaction**

**Problem:** Agent makes assumptions instead of asking.

**Solution:** Implement question tool for clarification.

---

## Conclusion

OpenCode's tool system demonstrates several key principles:

1. **Safety First:** Permission system prevents accidents
2. **Resilience:** Multiple strategies handle LLM imperfections
3. **User Experience:** Clear messages, progress updates, structured output
4. **Performance:** Automatic truncation, timeouts, efficient search
5. **Extensibility:** Clean architecture enables easy tool addition

By adopting these patterns in HIC, we can create a robust, reliable tool system that matches or exceeds OpenCode's capabilities.

### Next Steps

1. ✅ **This document** - Analysis complete
2. **Design detailed architecture** for HIC tools
3. **Implement Phase 1** - Foundation (Context, Permissions, ToolResult)
4. **Implement Phase 2** - Core Tools (Edit, Write, Bash, Read)
5. **Test extensively** - Unit, integration, security, performance
6. **Document** - API reference, examples, best practices
7. **Deploy** - Roll out new tools to HIC users

### Success Metrics

- **Reliability:** <5% tool failure rate
- **Performance:** <2s average tool execution time
- **Safety:** Zero accidental destructive operations
- **UX:** >90% user satisfaction with tool interactions
- **Coverage:** All core workflows supported by tools

---

**End of Analysis**
