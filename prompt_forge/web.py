"""Local web UI for Prompt Forge.

Pure stdlib (http.server, no Flask/Django needed). Opens your browser to a
page where you type naturally and get compiled prompts + optional execution.

Start with:  forge web
"""
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .compiler import PromptCompiler
from . import runner as runners
from . import doctor
from . import exporter


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔨 Prompt Forge</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0d0d0f; color: #e8e8ea; min-height: 100vh;
  }
  .wrap { max-width: 900px; margin: 0 auto; padding: 2rem 1rem 6rem; }
  header { display: flex; justify-content: space-between; align-items: center;
           margin-bottom: 2rem; }
  h1 { font-size: 1.5rem; margin: 0; font-weight: 600; }
  h1 .dim { color: #6b6b73; font-weight: 400; }
  .hw-badge { font-size: 0.78rem; color: #8a8a92; cursor: pointer; }
  .hw-badge:hover { color: #bbb; }
  textarea {
    width: 100%; min-height: 140px; padding: 1rem;
    background: #17171a; color: #e8e8ea;
    border: 1px solid #2a2a2f; border-radius: 10px;
    font-family: inherit; font-size: 1rem; resize: vertical;
  }
  textarea:focus { outline: none; border-color: #4a90e2; }
  .controls { display: flex; gap: 0.6rem; margin-top: 0.8rem; flex-wrap: wrap; }
  button, select {
    padding: 0.65rem 1.1rem; border-radius: 8px; border: 1px solid #2a2a2f;
    background: #17171a; color: #e8e8ea; cursor: pointer;
    font-family: inherit; font-size: 0.9rem;
  }
  button:hover, select:hover { background: #202025; }
  button.primary { background: #4a90e2; border-color: #4a90e2; color: #fff; }
  button.primary:hover { background: #3a7fd2; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  .meta { display: flex; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap;
          font-size: 0.82rem; color: #8a8a92; }
  .meta span { background: #17171a; padding: 0.3rem 0.7rem; border-radius: 6px; }
  .output {
    margin-top: 1.2rem; padding: 1rem;
    background: #0a0a0c; border: 1px solid #2a2a2f; border-radius: 10px;
    white-space: pre-wrap; font-family: "SF Mono", Consolas, monospace;
    font-size: 0.82rem; max-height: 500px; overflow-y: auto;
  }
  .response {
    margin-top: 1rem; padding: 1.2rem;
    background: #141419; border-left: 3px solid #4a90e2; border-radius: 6px;
    white-space: pre-wrap; font-size: 0.95rem; line-height: 1.55;
  }
  .response h2 { font-size: 0.85rem; color: #8a8a92; margin-top: 0;
                 text-transform: uppercase; letter-spacing: 0.05em; }
  .error { color: #ff6b6b; background: #2a0d0d; padding: 1rem;
           border-radius: 8px; margin-top: 1rem; }
  .section-title { color: #8a8a92; font-size: 0.82rem;
                   text-transform: uppercase; letter-spacing: 0.05em;
                   margin-top: 2rem; margin-bottom: 0.6rem; }
  .modal {
    position: fixed; inset: 0; background: rgba(0,0,0,0.7);
    display: none; align-items: center; justify-content: center; padding: 1rem;
    z-index: 100;
  }
  .modal.show { display: flex; }
  .modal-body {
    background: #17171a; padding: 1.5rem; border-radius: 10px;
    max-width: 500px; width: 100%;
  }
  .modal h2 { margin-top: 0; }
  .modal pre { background: #0a0a0c; padding: 0.8rem; border-radius: 6px;
               font-size: 0.8rem; overflow-x: auto; }
  .spinner {
    display: inline-block; width: 14px; height: 14px;
    border: 2px solid #333; border-top-color: #4a90e2;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 0.4rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🔨 Prompt Forge <span class="dim">— web</span></h1>
    <span class="hw-badge" id="hwBadge" onclick="showDoctor()">checking hardware...</span>
  </header>

  <textarea id="input" placeholder="Write what you need in plain language.
Any typos, any language — prompt-forge will clean it up and build a structured god-mode prompt."></textarea>

  <div class="controls">
    <button class="primary" onclick="compile(false)">Compile</button>
    <button class="primary" onclick="compile(true)" id="runBtn">Compile & Run</button>
    <select id="runner">
      <option value="auto">runner: auto</option>
      <option value="gemini">gemini</option>
      <option value="groq">groq</option>
      <option value="cerebras">cerebras</option>
      <option value="ollama">ollama</option>
    </select>
    <select id="format">
      <option value="">save: xml (default)</option>
      <option value="md">save: md</option>
      <option value="txt">save: txt</option>
      <option value="html">save: html</option>
      <option value="pdf">save: pdf</option>
      <option value="none">don't save</option>
    </select>
    <button onclick="copyOutput()">📋 Copy</button>
  </div>

  <div id="result"></div>
</div>

<div class="modal" id="doctorModal" onclick="if(event.target===this)hideDoctor()">
  <div class="modal-body">
    <h2>🩺 Hardware report</h2>
    <pre id="doctorContent">Loading...</pre>
    <button onclick="hideDoctor()">Close</button>
  </div>
</div>

<script>
let lastOutput = "";

async function compile(execute) {
  const text = document.getElementById("input").value.trim();
  if (!text) { alert("Write something first."); return; }
  const runner = document.getElementById("runner").value;
  const format = document.getElementById("format").value;
  const btn = document.querySelectorAll("button.primary");
  btn.forEach(b => b.disabled = true);

  const result = document.getElementById("result");
  result.innerHTML = '<div class="output"><span class="spinner"></span>working...</div>';

  try {
    const resp = await fetch("/api/compile", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text, execute, runner, format}),
    });
    const data = await resp.json();

    if (data.error) {
      result.innerHTML = `<div class="error"><b>Error:</b> ${escapeHtml(data.error)}</div>`;
      return;
    }

    lastOutput = data.response || data.xml;
    let html = "";
    html += `<div class="meta">
      <span>level: L${data.level}</span>
      <span>domain: ${data.domain}</span>
      ${data.techniques?.length ? `<span>techniques: ${data.techniques.join(", ")}</span>` : ""}
      ${data.saved_path ? `<span>saved: ${escapeHtml(data.saved_path)}</span>` : ""}
    </div>`;

    if (data.response) {
      html += `<div class="response">
        <h2>Response · ${data.runner_used} · ${data.model_used} · ${data.elapsed_s.toFixed(1)}s</h2>
        ${escapeHtml(data.response)}
      </div>`;
      html += `<div class="section-title">Compiled prompt that produced this</div>
               <div class="output">${escapeHtml(data.xml)}</div>`;
    } else {
      html += `<div class="section-title">Compiled prompt</div>
               <div class="output">${escapeHtml(data.xml)}</div>`;
    }
    result.innerHTML = html;
  } catch (e) {
    result.innerHTML = `<div class="error"><b>Network error:</b> ${escapeHtml(e.message)}</div>`;
  } finally {
    btn.forEach(b => b.disabled = false);
  }
}

async function copyOutput() {
  if (!lastOutput) { alert("Nothing to copy yet."); return; }
  try {
    await navigator.clipboard.writeText(lastOutput);
    alert("Copied!");
  } catch (e) {
    alert("Copy failed: " + e.message);
  }
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function loadHardware() {
  try {
    const resp = await fetch("/api/hardware");
    const data = await resp.json();
    const mode = data.recommendation.runner === "cloud" ? "cloud" : "local";
    document.getElementById("hwBadge").textContent =
      `${data.profile.ram_gb}GB RAM · ${data.profile.cpu_cores} cores · ${mode} recommended`;
    window._hwData = data;
  } catch (e) {
    document.getElementById("hwBadge").textContent = "hardware check failed";
  }
}

function showDoctor() {
  const modal = document.getElementById("doctorModal");
  const pre = document.getElementById("doctorContent");
  if (window._hwData) {
    pre.textContent = JSON.stringify(window._hwData, null, 2);
  }
  modal.classList.add("show");
}
function hideDoctor() { document.getElementById("doctorModal").classList.remove("show"); }

loadHardware();

// Ctrl/Cmd+Enter to compile
document.getElementById("input").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    compile(true);
  }
});
</script>
</body>
</html>
"""


class ForgeHandler(BaseHTTPRequestHandler):
    compiler: PromptCompiler = None  # set at server start

    def log_message(self, format, *args):  # silence default HTTP log spam
        pass

    def _send_json(self, obj: dict, status: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/hardware":
            try:
                profile = doctor.detect()
                rec = doctor.recommend(profile)
                self._send_json({
                    "profile": profile.to_dict(),
                    "recommendation": {
                        "runner": rec.runner,
                        "reason": rec.reason,
                        "ollama_model": rec.ollama_model,
                        "warnings": rec.warnings,
                        "cloud_priority": rec.cloud_priority,
                    },
                })
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/compile":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            text = payload.get("text", "").strip()
            execute = bool(payload.get("execute", False))
            runner_choice = payload.get("runner") or "auto"
            fmt = payload.get("format") or None

            if not text:
                return self._send_json({"error": "empty input"}, status=400)

            result = self.compiler.compile(text)
            response = {
                "xml": result.xml,
                "level": result.level,
                "domain": result.domain,
                "techniques": result.techniques,
                "assumptions": result.assumptions,
            }

            if execute:
                try:
                    run_result = runners.run(result.xml, runner=runner_choice)
                    response["response"] = run_result.text
                    response["runner_used"] = run_result.runner
                    response["model_used"] = run_result.model
                    response["elapsed_s"] = run_result.elapsed_s
                except runners.RunnerError as e:
                    return self._send_json({"error": f"runner failed: {e}"},
                                           status=500)

            # Save if format isn't "none"
            if fmt != "none":
                save_fmt = fmt if fmt else "xml"
                try:
                    if execute:
                        saved = exporter.export_run_output(
                            run_text=response.get("response", result.xml),
                            raw_input=text,
                            metadata={"level": result.level,
                                      "domain": result.domain,
                                      "runner": response.get("runner_used"),
                                      "model": response.get("model_used"),
                                      "elapsed_s": response.get("elapsed_s", 0)},
                            fmt=save_fmt,
                        )
                    else:
                        saved = exporter.export_prompt(
                            xml=result.xml,
                            raw_input=text,
                            metadata={"level": result.level,
                                      "domain": result.domain,
                                      "techniques": result.techniques},
                            fmt=save_fmt,
                        )
                    response["saved_path"] = str(saved)
                except Exception as e:
                    response["save_error"] = str(e)

            self._send_json(response)
        except Exception as e:
            self._send_json({"error": f"server error: {e}"}, status=500)


def serve(host: str = "127.0.0.1", port: int = 7788,
          open_browser: bool = True) -> None:
    ForgeHandler.compiler = PromptCompiler()
    server = ThreadingHTTPServer((host, port), ForgeHandler)
    url = f"http://{host}:{port}"
    print(f"\n🔨 Prompt Forge web UI → {url}")
    print("   (Ctrl+C to stop)\n")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ Stopped.")
        server.shutdown()
