const state = {
  jobId: null,
  timer: null,
};

const els = {
  dropZone: document.getElementById("drop-zone"),
  fileInput: document.getElementById("file-input"),
  uploadError: document.getElementById("upload-error"),
  previewCard: document.getElementById("preview-card"),
  resultsCard: document.getElementById("results-card"),
  fileName: document.getElementById("file-name"),
  stats: document.getElementById("stats"),
  phoneFields: document.getElementById("phone-fields"),
  runBtn: document.getElementById("run-btn"),
  cancelBtn: document.getElementById("cancel-btn"),
  resetBtn: document.getElementById("reset-btn"),
  progressWrap: document.getElementById("progress-wrap"),
  progressFill: document.getElementById("progress-fill"),
  progressLabel: document.getElementById("progress-label"),
  jobError: document.getElementById("job-error"),
  resultSummary: document.getElementById("result-summary"),
  dlOn: document.getElementById("dl-on"),
  dlOff: document.getElementById("dl-off"),
  dlFail: document.getElementById("dl-fail"),
};

function show(el, on = true) {
  el.classList.toggle("hidden", !on);
}

function setError(node, message) {
  node.textContent = message || "";
  show(node, Boolean(message));
}

function stat(label, value) {
  return `<div class="stat"><b>${value}</b><span>${label}</span></div>`;
}

function renderJob(job) {
  els.fileName.textContent = job.filename;
  const fields = job.phone_fields || [];
  els.phoneFields.textContent = fields.length
    ? `Checking: ${fields.join(", ")}`
    : "";
  show(els.phoneFields, fields.length > 0);
  const s = job.stats;
  els.stats.innerHTML = [
    stat("rows", s.rows),
    stat("to check", job.total_to_check),
    stat("invalid", s.invalid),
    stat("duplicates", s.duplicates),
    stat("on TPS", s.on_tps),
    stat("not on TPS", s.not_on_tps),
  ].join("");

  const running = job.status === "running";
  const canRun =
    (job.status === "ready" || job.status === "paused" || job.status === "cancelled") &&
    s.valid > 0;
  els.runBtn.disabled = !canRun || running;
  els.runBtn.textContent =
    job.status === "paused" || job.status === "cancelled"
      ? "Resume TPS Scan"
      : "Run TPS Scan";
  show(els.cancelBtn, running);
  show(els.progressWrap, running || job.status === "complete" || job.status === "paused");

  const pct = job.total_to_check
    ? Math.min(100, Math.round((job.checked / job.total_to_check) * 100))
    : 0;
  els.progressFill.style.width = `${pct}%`;
  if (running) {
    els.progressLabel.textContent = job.current_number
      ? `Checking ${job.current_number} · ${job.checked} of ${job.total_to_check}`
      : `Starting scan · ${job.checked} of ${job.total_to_check}`;
  } else if (job.status === "paused") {
    els.progressLabel.textContent = `Paused at ${job.checked} of ${job.total_to_check}`;
  } else if (job.status === "complete") {
    els.progressLabel.textContent = `Finished ${job.checked} of ${job.total_to_check}`;
  }

  setError(els.jobError, job.error);

  const done = job.status === "complete" || job.checked > 0;
  show(els.resultsCard, done);
  els.dlOn.href = `/api/jobs/${job.id}/download/on-tps`;
  els.dlOff.href = `/api/jobs/${job.id}/download/not-on-tps`;
  els.dlFail.href = `/api/jobs/${job.id}/download/failed`;
  els.resultSummary.textContent = `${s.on_tps} on TPS · ${s.not_on_tps} not on TPS · ${s.failed + s.invalid} failed or invalid`;
}

async function readError(response) {
  try {
    const data = await response.json();
    return data.detail || "Request failed";
  } catch {
    return "Request failed";
  }
}

async function refreshJob() {
  if (!state.jobId) return;
  const response = await fetch(`/api/jobs/${state.jobId}`);
  if (!response.ok) return;
  const job = await response.json();
  renderJob(job);
  if (job.status !== "running") {
    clearInterval(state.timer);
    state.timer = null;
  }
}

function poll() {
  if (state.timer) return;
  state.timer = setInterval(refreshJob, 1000);
}

async function uploadFile(file) {
  setError(els.uploadError, "");
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/jobs", { method: "POST", body });
  if (!response.ok) {
    setError(els.uploadError, await readError(response));
    return;
  }
  const job = await response.json();
  state.jobId = job.id;
  show(els.previewCard, true);
  show(els.resultsCard, false);
  renderJob(job);
}

els.fileInput.addEventListener("change", () => {
  if (els.fileInput.files[0]) uploadFile(els.fileInput.files[0]);
});
["dragenter", "dragover"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.add("drag");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.remove("drag");
  });
});
els.dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (file) uploadFile(file);
});

els.runBtn.addEventListener("click", async () => {
  if (!state.jobId) return;
  els.runBtn.disabled = true;
  const response = await fetch(`/api/jobs/${state.jobId}/start`, { method: "POST" });
  if (!response.ok) {
    setError(els.jobError, await readError(response));
    els.runBtn.disabled = false;
    return;
  }
  renderJob(await response.json());
  poll();
});

els.cancelBtn.addEventListener("click", async () => {
  if (!state.jobId) return;
  await fetch(`/api/jobs/${state.jobId}/cancel`, { method: "POST" });
  refreshJob();
});

els.resetBtn.addEventListener("click", () => {
  state.jobId = null;
  clearInterval(state.timer);
  state.timer = null;
  els.fileInput.value = "";
  show(els.previewCard, false);
  show(els.resultsCard, false);
  setError(els.uploadError, "");
});
