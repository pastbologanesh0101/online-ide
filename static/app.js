const codeBox = document.getElementById("code");
const stdinBox = document.getElementById("stdin-box");
const runBtn = document.getElementById("run-btn");
const saveBtn = document.getElementById("save-btn");
const refreshBtn = document.getElementById("refresh-btn");
const snippetSelect = document.getElementById("snippet-select");
const snippetNameInput = document.getElementById("snippet-name");
const statusEl = document.getElementById("status");
const stdoutEl = document.getElementById("stdout");
const stderrEl = document.getElementById("stderr");
const exitCodeEl = document.getElementById("exit-code");
const execTimeEl = document.getElementById("exec-time");

async function runCode() {
  statusEl.textContent = "Running...";
  runBtn.disabled = true;
  stdoutEl.textContent = "";
  stderrEl.textContent = "";
  exitCodeEl.textContent = "";
  execTimeEl.textContent = "";

  try {
    const resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_code: codeBox.value,
        stdin: stdinBox.value,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      statusEl.textContent = "Error";
      stderrEl.textContent = data.error || "Unknown error";
      return;
    }
    stdoutEl.textContent = data.stdout || "";
    stderrEl.textContent = data.stderr || "";
    exitCodeEl.textContent = `exit code: ${data.exit_code === null ? "n/a (timed out)" : data.exit_code}`;
    execTimeEl.textContent = `time: ${data.execution_time.toFixed(3)}s`;
    statusEl.textContent = data.timed_out ? "Timed out" : "Done";
  } catch (err) {
    statusEl.textContent = "Request failed";
    stderrEl.textContent = String(err);
  } finally {
    runBtn.disabled = false;
  }
}

async function saveSnippet() {
  const name = snippetNameInput.value.trim();
  if (!name) {
    statusEl.textContent = "Enter a snippet name first";
    return;
  }
  const resp = await fetch("/api/snippets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, source_code: codeBox.value }),
  });
  if (resp.ok) {
    statusEl.textContent = `Saved '${name}'`;
    await refreshSnippetList();
  } else {
    const data = await resp.json();
    statusEl.textContent = data.error || "Save failed";
  }
}

async function refreshSnippetList() {
  const resp = await fetch("/api/snippets");
  const snippets = await resp.json();
  snippetSelect.innerHTML = '<option value="">-- load saved snippet --</option>';
  for (const s of snippets) {
    const opt = document.createElement("option");
    opt.value = s.name;
    opt.textContent = s.name;
    snippetSelect.appendChild(opt);
  }
}

async function loadSnippet(name) {
  if (!name) return;
  const resp = await fetch(`/api/snippets/${encodeURIComponent(name)}`);
  if (resp.ok) {
    const data = await resp.json();
    codeBox.value = data.source_code;
    snippetNameInput.value = name;
    statusEl.textContent = `Loaded '${name}'`;
  }
}

runBtn.addEventListener("click", runCode);
saveBtn.addEventListener("click", saveSnippet);
refreshBtn.addEventListener("click", refreshSnippetList);
snippetSelect.addEventListener("change", (e) => loadSnippet(e.target.value));

refreshSnippetList();
