"""
sandbox.py
==========

Plain, importable, directly-testable module that executes untrusted Python
source code in a **separate subprocess** with best-effort safety limits.

This module never uses eval()/exec() on untrusted code in the same process
as the caller (e.g. the Flask server). All execution happens via
``subprocess.run([sys.executable, script_path], ...)`` so a crash, infinite
loop, or memory blow-up in the submitted code cannot take down the caller.

SECURITY SCOPE
--------------
This provides *defense in depth for a trusted, local, single-user demo*,
NOT a real multi-tenant sandbox. See README.md for the full disclaimer.
Safety measures implemented here:

  * Hard wall-clock execution timeout (subprocess is killed if exceeded).
  * Best-effort memory/CPU resource limits via ``resource.setrlimit`` on
    POSIX systems (applied in the child process before exec, via the
    ``preexec_fn`` hook).
  * A fresh, isolated temporary directory per execution, used as the
    subprocess's cwd and removed afterward (even on timeout/crash).
  * A stripped-down environment for the child process (no inherited
    secrets), and no special network isolation beyond that (documented
    limitation -- see README).
  * Clean capture of stdout, stderr, exit code, and wall-clock execution
    time, regardless of whether the child succeeded, errored, or timed out.
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import subprocess
import sys
import tempfile
import time
import shutil

try:
    import resource  # POSIX only
    HAVE_RESOURCE = True
except ImportError:  # pragma: no cover - Windows fallback
    resource = None
    HAVE_RESOURCE = False

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS = 5
# 256 MB default address-space limit for the executed child process.
DEFAULT_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
DEFAULT_CPU_LIMIT_SECONDS = 5


@dataclasses.dataclass
class ExecutionResult:
    """Result of running a piece of code in the sandbox."""

    stdout: str
    stderr: str
    exit_code: int | None
    execution_time: float
    timed_out: bool = False

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "timed_out": self.timed_out,
        }


def _limit_resources(memory_limit_bytes: int, cpu_limit_seconds: int):
    """
    Returns a callable suitable for subprocess.run(preexec_fn=...) that
    applies POSIX resource limits inside the freshly-forked child, before
    the user's script is exec'd. Only used on POSIX platforms.
    """

    def _apply():
        try:
            if memory_limit_bytes:
                # Limit total address space. Using RLIMIT_AS is the most
                # reliable way to bound a Python process's memory use.
                resource.setrlimit(
                    resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes)
                )
        except (ValueError, OSError):
            # Some platforms (e.g. macOS) restrict RLIMIT_AS; ignore and
            # rely on the timeout as a backstop.
            pass
        try:
            if cpu_limit_seconds:
                resource.setrlimit(
                    resource.RLIMIT_CPU, (cpu_limit_seconds, cpu_limit_seconds)
                )
        except (ValueError, OSError):
            pass
        try:
            # Prevent forking a swarm of child processes.
            resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        except (ValueError, OSError, AttributeError):
            pass

    return _apply


def run_python_code(
    source_code: str,
    stdin_input: str = "",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
    cpu_limit_seconds: int = DEFAULT_CPU_LIMIT_SECONDS,
) -> ExecutionResult:
    """
    Execute ``source_code`` as a standalone Python script in a fresh temp
    directory, in a separate subprocess, and return an ExecutionResult.

    The temp directory is always removed before returning, whether the
    execution succeeded, errored, or timed out.
    """
    tmp_dir = tempfile.mkdtemp(prefix="online_ide_run_")
    script_path = os.path.join(tmp_dir, "main.py")

    try:
        with open(script_path, "w") as f:
            f.write(source_code)

        # Minimal environment: no inherited secrets/network config beyond
        # what's needed to find the Python interpreter and stdlib.
        restricted_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            # Prevent writing bytecode into the temp dir / polluting cache.
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        preexec_fn = None
        if HAVE_RESOURCE and os.name == "posix":
            preexec_fn = _limit_resources(memory_limit_bytes, cpu_limit_seconds)

        start = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                [sys.executable, script_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp_dir,
                env=restricted_env,
                preexec_fn=preexec_fn,
            )
            stdout, stderr, exit_code = (
                completed.stdout,
                completed.stderr,
                completed.returncode,
            )
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (
                exc.stdout.decode(errors="replace") if exc.stdout else ""
            )
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (
                exc.stderr.decode(errors="replace") if exc.stderr else ""
            )
            stderr += f"\n[sandbox] Execution timed out after {timeout} seconds and was terminated.\n"
            exit_code = None
        finally:
            elapsed = time.monotonic() - start

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time=elapsed,
            timed_out=timed_out,
        )
    finally:
        # Always clean up the temp directory, no leftovers.
        with contextlib.suppress(Exception):
            shutil.rmtree(tmp_dir, ignore_errors=True)
