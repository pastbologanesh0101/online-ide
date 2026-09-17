"""
Unit tests for sandbox.py -- direct calls, no Flask involved.

Timeouts are kept short (1-2s) so the whole suite runs quickly, including
the infinite-loop test which must actually be killed within bounded time.
"""

from __future__ import annotations

import glob
import os
import tempfile
import unittest

import sandbox


class TestSandboxExecution(unittest.TestCase):
    def test_correct_code_executes_and_returns_expected_stdout(self):
        result = sandbox.run_python_code("print('hello from sandbox')")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hello from sandbox", result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.timed_out)

    def test_syntax_error_returns_clear_error_and_nonzero_exit(self):
        result = sandbox.run_python_code("def broken(:\n    pass")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNotNone(result.exit_code)
        self.assertIn("SyntaxError", result.stderr)
        self.assertFalse(result.timed_out)

    def test_infinite_loop_is_killed_by_timeout(self):
        # Short timeout keeps this test fast while still proving the
        # subprocess is actually terminated, not left running.
        result = sandbox.run_python_code(
            "while True:\n    pass\n", timeout=1
        )
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertLess(result.execution_time, 5)  # bounded, not hung
        self.assertIn("timed out", result.stderr.lower())

    def test_stdin_input_is_available_to_the_script(self):
        code = "name = input()\nprint(f'hi {name}')"
        result = sandbox.run_python_code(code, stdin_input="world\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("hi world", result.stdout)

    def test_stdin_with_multiple_lines(self):
        code = (
            "import sys\n"
            "lines = sys.stdin.read().splitlines()\n"
            "print(sum(int(x) for x in lines))\n"
        )
        result = sandbox.run_python_code(code, stdin_input="1\n2\n3\n")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("6", result.stdout)

    def test_exception_traceback_captured_in_stderr(self):
        code = "raise ValueError('boom')"
        result = sandbox.run_python_code(code)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("ValueError", result.stderr)
        self.assertIn("boom", result.stderr)
        self.assertIn("Traceback", result.stderr)

    def test_temp_directories_are_cleaned_up_after_execution(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "online_ide_run_*")))
        sandbox.run_python_code("print('cleanup check')")
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "online_ide_run_*")))
        # No leftover temp dirs created by this run should remain.
        self.assertEqual(after - before, set())

    def test_temp_directories_cleaned_up_even_on_timeout(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "online_ide_run_*")))
        sandbox.run_python_code("while True:\n    pass\n", timeout=1)
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "online_ide_run_*")))
        self.assertEqual(after - before, set())

    def test_memory_limit_does_not_crash_caller(self):
        # Attempt to allocate far more than the (small) limit we set here.
        # Expect either a MemoryError inside the subprocess (nonzero exit,
        # captured cleanly) or the OS/py killing it -- but this test process
        # itself must never hang or crash.
        code = (
            "data = []\n"
            "for _ in range(10**7):\n"
            "    data.append('x' * 10_000)\n"
            "print('should not get here')\n"
        )
        result = sandbox.run_python_code(
            code, timeout=5, memory_limit_bytes=64 * 1024 * 1024
        )
        # The important assertion: this call returned at all (no hang) and
        # the calling process is still alive to check the result.
        self.assertIsInstance(result, sandbox.ExecutionResult)
        # It must not have "succeeded" as if nothing happened.
        self.assertTrue(
            result.timed_out
            or result.exit_code != 0
            or "should not get here" not in result.stdout
        )

    def test_execution_time_is_recorded_and_positive(self):
        result = sandbox.run_python_code("print('timing')")
        self.assertGreaterEqual(result.execution_time, 0)

    def test_exit_code_nonzero_on_sys_exit(self):
        result = sandbox.run_python_code("import sys\nsys.exit(3)")
        self.assertEqual(result.exit_code, 3)


if __name__ == "__main__":
    unittest.main()
