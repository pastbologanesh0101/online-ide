# Online IDE

A small, self-contained browser-based Python code runner: write Python in
the browser, click **Run**, see stdout/stderr/exit code/execution time, and
save/reload named snippets. Built with Flask + SQLite, no frontend build
step, no external editor dependency (a plain `<textarea>`).

## ⚠️ Security scope — read this first

**This is a local, single-user demo/portfolio tool.** It executes submitted
code in a restricted subprocess on the machine running the Flask server.

It is **explicitly NOT safe to deploy as a public, multi-tenant service**
as-is. A `subprocess` with resource limits and a timeout is defense in
depth for a *trusted single user running their own code on their own
machine* — it is **not** a real sandbox. Anyone who can reach the `/api/run`
endpoint can run arbitrary Python with the privileges of the process
running Flask (filesystem access within OS permissions, ability to spawn
processes, etc).

If you ever wanted to expose something like this to untrusted users over
the network, you would need a real isolation layer — e.g. **gVisor**,
**Docker with a locked-down security profile + seccomp + no host mounts**,
**Firecracker microVMs**, or a managed code-execution API — plus network
egress blocking at the OS/container level, CPU/PID/file-descriptor limits,
and non-root execution. None of that is implemented here. Treat this repo
as a demonstration of the *shape* of a sandboxed execution pipeline, not a
production-ready one.

### What IS implemented (real, meaningful, but best-effort)

- **Separate subprocess, always.** The Flask process never calls
  `eval()`/`exec()` on submitted code. Code is written to a file and run
  via `subprocess.run([sys.executable, path], ...)` in a child process, so
  a crash or hang in submitted code cannot take down the web server.
- **Hard execution timeout.** `subprocess.run(..., timeout=N)` kills the
  child if it runs longer than `N` seconds (configurable per-request, with
  a hard server-side ceiling).
- **Best-effort memory/CPU limits on POSIX** via `resource.setrlimit`
  (`RLIMIT_AS` for address space, `RLIMIT_CPU` for CPU time, `RLIMIT_NPROC`
  to stop fork bombs), applied in the child before the script runs. Some
  platforms (notably macOS) restrict `RLIMIT_AS`, in which case the
  timeout is the practical backstop.
- **Fresh temp directory per execution**, used as the subprocess's working
  directory and removed immediately after execution (success, error, or
  timeout).
- **Restricted environment variables** for the child process — it does not
  inherit the full environment of the Flask server (no ambient secrets).
- **No network sandboxing is actually enforced** — this is a documented
  limitation, not a feature. Submitted code *can* make outbound network
  calls if the host allows it. If you need to guarantee no network access,
  run this inside a container/VM with egress firewalled off, or add
  something like `unshare --net` (Linux-only) in front of the subprocess
  call.

## Features

- Run Python 3 source code (Python only — other languages would need their
  own per-language sandboxing and are out of scope for this project).
- Optional stdin input for programs that call `input()` / read `sys.stdin`.
- Clean capture of stdout, stderr, exit code, and wall-clock execution time.
- Timeout handling that reports a clear "timed out" status instead of
  hanging the request.
- Save and reload named code snippets, persisted in a local SQLite database.
- Minimal, dependency-free frontend (plain HTML/CSS/JS, a `<textarea>` for
  the editor).

## Project layout

```
online-ide/
├── app.py              # Flask routes (HTTP <-> sandbox.py / db.py)
├── sandbox.py           # Execution sandbox — plain, importable, testable
├── db.py                 # SQLite snippet storage
├── templates/index.html  # Frontend page
├── static/style.css      # Frontend styling
├── static/app.js         # Frontend logic (fetch calls to the API)
├── tests/                 # unittest test suite (22 tests)
└── .github/workflows/tests.yml  # CI: runs tests on Python 3.11 and 3.12
```

## Running it locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in a browser.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

The suite covers (direct calls to `sandbox.py`, `db.py`, and via Flask's
test client):

- Correct code executes and returns expected stdout.
- A syntax error returns a clear error message and nonzero exit code
  instead of crashing the server.
- An infinite loop is killed by the timeout (bounded test time, ~1s
  timeout) and reported as timed out.
- Code that reads from stdin works when input is provided.
- An uncaught exception's traceback is captured in stderr with a nonzero
  exit code.
- Saving then loading a snippet round-trips the exact source code.
- Temp directories are cleaned up after every execution (including on
  timeout) — asserted via a before/after glob of the temp directory.
- Hitting the memory limit doesn't crash or hang the Flask process — it's
  handled as a contained subprocess failure.
- Flask endpoints for running code and for the snippet save/load API.

## Example usage

1. Open the app, type `print("hello world")` in the editor, click **Run**.
2. See `hello world` appear under **Output**, exit code `0`.
3. Try a program that reads input:
   ```python
   name = input()
   print(f"hello, {name}")
   ```
   put `Ada` in the stdin box, click **Run** → output is `hello, Ada`.
4. Type a snippet name (e.g. `greeter`) and click **Save**. Reload the page,
   pick `greeter` from the dropdown to load it back.
5. Try `while True: pass` to see the timeout in action — it reports a
   timed-out status instead of hanging.

## License

MIT — see [LICENSE](LICENSE).
