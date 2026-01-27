# Agent Demo: read / write / edit tools

This example shows a safe, self-contained flow where the agent reads a file,
writes a new file, and edits it using the builtin tools. It operates entirely in

## Files used
- `notes.md` (dummy content created by the example)
- `script.py` (dummy file created and edited)

## Steps performed
1. Write `notes.md` with two lines of text using the `write` tool.
2. Read `notes.md` with pagination (limit 1) using the `read` tool.
3. Edit `notes.md` to change the first line using the `edit` tool.
4. Write a small `script.py` stub, then edit it to add a function.
5. Read the updated files to verify changes.

## How to run (pseudo-flow)
```text
1) Create an Agent with no explicit tools (defaults will load bash/read/write/edit).
2) Run a task like: "Create notes.md with two lines, show the first line, then rename
   the first line to 'Updated heading'. Also create script.py with a hello() function
   that returns 'hi'."
3) The agent should call:
   - write(notes.md, ...)
   - read(notes.md, offset=0, limit=1)
   - edit(notes.md, old='First line', new='Updated heading')
   - write(script.py, ...)
   - edit(script.py, old='pass', new='    return "hi"')
   - read(script.py, offset=0, limit=50)
```

## Safety
- Uses only files inside the working directory you provide.
- No modification of core repo files.
- Suitable for local dry runs or CI examples.
