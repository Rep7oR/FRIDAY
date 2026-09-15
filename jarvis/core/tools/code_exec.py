"""Sandboxed short-lived Python execution, for quick calculations/data munging."""
from __future__ import annotations

import subprocess
import sys

from jarvis import config
from jarvis.core.tools.base import Tool

MAX_OUTPUT_CHARS = 4_000
DEFAULT_TIMEOUT_SECONDS = 10


class RunPythonTool(Tool):
    name = "run_python"
    description = (
        "Run a short Python snippet in an isolated subprocess (cwd = the workspace sandbox) "
        "and return its stdout/stderr. Use for calculations, quick data processing, etc. "
        "No network or filesystem access beyond the workspace is guaranteed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute."},
            "timeout_seconds": {
                "type": "integer",
                "description": f"Max run time in seconds (default {DEFAULT_TIMEOUT_SECONDS}).",
            },
        },
        "required": ["code"],
    }

    def run(self, code: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
        timeout_seconds = max(1, min(int(timeout_seconds), 30))
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(config.WORKSPACE_DIR),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return f"Error: execution timed out after {timeout_seconds}s."

        stdout = result.stdout[-MAX_OUTPUT_CHARS:]
        stderr = result.stderr[-MAX_OUTPUT_CHARS:]
        parts = [f"exit_code: {result.returncode}"]
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        return "\n".join(parts)
