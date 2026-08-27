const state = {
  jobId: null,
  timer: null,
  job: null,
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
  etaLabel: document.getElementById("eta-label"),
  etaSub: document.getElementById("eta-sub"),
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

function formatDuration(seconds) {
  seconds = Math.max(0, Math.round(Number(seconds) || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${rest}s`;
  return `${rest}s`;
}

function waitSeconds(job) {
  if (!job || !job.wait_until) return 0;
  return Math.max(0, Math.round((Date.parse(job.wait_until) - Date.now()) / 1000));
}

function etaSeconds(job) {
  if (!job || job.status !== "running") return 0;
  const wait = waitSeconds(job);
  const remaining = Math.max(0, (job.remaining ?? job.total_to_check - job.checked) || 0);
  const pace = job.seconds_per_check || 20;
  return Math.round(remaining * pace + wait);
}

function renderProgress(job) {
  const pct = job.total_to_check
    ? Math.min(100, Math.round((job.checked / job.total_to_check) * 100))
    : 0;
  els.progressFill.style.width = `${pct}%`;

  const wait = waitSeconds(job);
  const eta = etaSeconds(job);
  const running = job.status === "running";

  if (running && wait > 0) {
    els.etaLabel.textContent = `Resuming in ${formatDuration(wait)}`;
    els.etaLabel.classList.add("waiting");
  } else if (running) {
    els.etaLabel.textContent = `About ${formatDuration(eta)} left`;
    els.etaLabel.classList.remove("waiting");
  } else if (job.status === "complete") {
    els.etaLabel.textContent = `Finished in ${formatDuration(job.elapsed_seconds)}`;
    els.etaLabel.classList.remove("waiting");
  } else if (job.status === "paused") {
    els.etaLabel.textContent = `Paused · ${formatDuration(eta)} remaining`;
    els.etaLabel.classList.remove("waiting");
  } else {
    els.etaLabel.textContent = "About — left";
    els.etaLabel.classList.remove("waiting");
  }

  if (running && wait > 0) {
    els.progressLabel.textContent =
      job.wait_reason ||
      `TPS rate limit · ${job.checked} of ${job.total_to_check} checked`;
  } else if (running) {
    els.progressLabel.textContent = job.current_number
      ? `Checking ${job.current_number} · ${job.checked} of ${job.total_to_check}`
      : `Starting scan · ${job.checked} of ${job.total_to_check}`;
  } else if (job.status === "paused") {
    els.progressLabel.textContent = `Paused at ${job.checked} of ${job.total_to_check}`;
  } else if (job.status === "complete") {
    els.progressLabel.textContent = `Finished ${job.checked} of ${job.total_to_check}`;
  }

  const parts = [];
  if (job.elapsed_seconds) parts.push(`${formatDuration(job.elapsed_seconds)} elapsed`);
  if (job.seconds_per_check && job.checked) {
    parts.push(`${formatDuration(job.seconds_per_check)} per number`);
  }
  if (running) parts.push(`${pct}% done`);
  els.etaSub.textContent = parts.join(" · ");
}

function renderJob(job) {
  state.job = job;
  els.fileName.textContent = job.filename;
  const fields = job.phone_fields || [];
  const filterBits = [];
  if (fields.length) filterBits.push(`Checking: ${fields.join(", ")}`);
  if (job.status_filter) {
    filterBits.push(
      `${job.status_filter} only (${job.status_field || "Status"})`
    );
  }
  els.phoneFields.textContent = filterBits.join(" · ");
  show(els.phoneFields, filterBits.length > 0);
  const s = job.stats;
  const cards = [
    stat("rows", s.rows),
    stat("to check", job.total_to_check),
    stat("invalid", s.invalid),
    stat("duplicates", s.duplicates),
  ];
  if (s.skipped) cards.push(stat("not active", s.skipped));
  cards.push(stat("on TPS", s.on_tps), stat("not on TPS", s.not_on_tps));
  els.stats.innerHTML = cards.join("");

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
  renderProgress(job);

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
  state.timer = setInterval(() => {
    if (state.job && state.job.status === "running") {
      renderProgress(state.job);
    }
    refreshJob();
  }, 1000);
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
  state.job = null;
  clearInterval(state.timer);
  state.timer = null;
  els.fileInput.value = "";
  show(els.previewCard, false);
  show(els.resultsCard, false);
  setError(els.uploadError, "");
});
