"""File tools, sandboxed to a single workspace directory so the agent can't touch the rest
of the filesystem."""
from __future__ import annotations

from pathlib import Path

from jarvis import config
from jarvis.core.tools.base import Tool

MAX_READ_BYTES = 200_000
MAX_WRITE_BYTES = 1_000_000


class SandboxError(Exception):
    pass


def _resolve(path: str) -> Path:
    """Resolve a user-supplied relative path inside WORKSPACE_DIR, rejecting escapes."""
    workspace = config.WORKSPACE_DIR.resolve()
    candidate = (workspace / path).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError:
        raise SandboxError(
            f"Path '{path}' escapes the sandboxed workspace ({workspace})."
        ) from None
    return candidate


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a text file from the local workspace sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            }
        },
        "required": ["path"],
    }

    def run(self, path: str) -> str:
        try:
            target = _resolve(path)
        except SandboxError as exc:
            return f"Error: {exc}"
        if not target.exists():
            return f"Error: '{path}' does not exist in the workspace."
        if not target.is_file():
            return f"Error: '{path}' is not a file."
        data = target.read_bytes()
        if len(data) > MAX_READ_BYTES:
            return f"Error: '{path}' is too large to read ({len(data)} bytes)."
        return data.decode("utf-8", errors="replace")


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write (create or overwrite) a text file in the local workspace sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            },
            "content": {"type": "string", "description": "Text content to write."},
        },
        "required": ["path", "content"],
    }

    def run(self, path: str, content: str) -> str:
        try:
            target = _resolve(path)
        except SandboxError as exc:
            return f"Error: {exc}"
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return f"Error: content too large ({len(encoded)} bytes, max {MAX_WRITE_BYTES})."
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded)
        return f"Wrote {len(encoded)} bytes to '{path}'."


class ListFilesTool(Tool):
    name = "list_files"
    description = "List files and directories under a path in the local workspace sandbox."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root (default: the root itself).",
            }
        },
        "required": [],
    }

    def run(self, path: str = ".") -> str:
        try:
            target = _resolve(path)
        except SandboxError as exc:
            return f"Error: {exc}"
        if not target.exists():
            return f"Error: '{path}' does not exist in the workspace."
        if not target.is_dir():
            return f"Error: '{path}' is not a directory."
        entries = sorted(target.iterdir(), key=lambda p: p.name)
        if not entries:
            return f"'{path}' is empty."
        lines = []
        for entry in entries:
            kind = "dir" if entry.is_dir() else "file"
            lines.append(f"[{kind}] {entry.name}")
        return "\n".join(lines)
