const tabs = Array.from(document.querySelectorAll('.tool-tab'));
const panels = Array.from(document.querySelectorAll('.tool-panel'));
const statusEl = document.getElementById('job-status');
const terminalEl = document.getElementById('terminal-log');
const artifactListEl = document.getElementById('artifact-list');
const apiOrigin = window.location.port === '8450'
  ? window.location.origin
  : `${window.location.protocol}//${window.location.hostname}:8450`;

let activeJobId = null;
let pollTimer = null;

function apiUrl(path) {
  return `${apiOrigin}${path}`;
}

function setStatus(text, state = '') {
  if (!statusEl) return;
  statusEl.textContent = text;
  statusEl.classList.remove('is-running', 'is-succeeded', 'is-failed');
  if (state) statusEl.classList.add(state);
}

function setLogText(text) {
  if (!terminalEl) return;
  terminalEl.textContent = text || 'No log output yet.';
  terminalEl.scrollTop = terminalEl.scrollHeight;
}

function renderArtifacts(jobId, artifacts) {
  if (!artifactListEl) return;
  artifactListEl.innerHTML = '';

  if (!artifacts || artifacts.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'artifact-empty';
    empty.textContent = 'No files yet.';
    artifactListEl.appendChild(empty);
    return;
  }

  artifacts.forEach((artifact) => {
    const item = document.createElement('div');
    item.className = 'artifact-item';

    const meta = document.createElement('div');
    meta.className = 'artifact-meta';

    const label = document.createElement('span');
    label.className = 'artifact-label';
    label.textContent = artifact.label || 'File';

    const name = document.createElement('span');
    name.className = 'artifact-name';
    name.textContent = artifact.name || 'download';

    meta.appendChild(label);
    meta.appendChild(name);

    const link = document.createElement('a');
    link.className = 'artifact-download';
    link.textContent = 'Download';
    link.href = apiUrl(`/api/jobs/${jobId}/artifacts/${artifact.id}`);
    link.target = '_blank';
    link.rel = 'noopener';

    item.appendChild(meta);
    item.appendChild(link);
    artifactListEl.appendChild(item);
  });
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function setFormsDisabled(disabled) {
  document.querySelectorAll('.tool-form button[type="submit"]').forEach((button) => {
    button.disabled = disabled;
  });
}

async function pollJob(jobId) {
  try {
    const response = await fetch(apiUrl(`/api/jobs/${jobId}`), { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Job fetch failed (${response.status})`);
    }

    const job = await response.json();
    const logs = Array.isArray(job.logs) ? job.logs.join('\n') : '';
    setLogText(logs);
    renderArtifacts(job.id, job.artifacts);

    if (job.status === 'queued' || job.status === 'running') {
      setStatus(job.status === 'queued' ? 'Queued' : 'Running', 'is-running');
      pollTimer = setTimeout(() => pollJob(jobId), 1250);
      return;
    }

    setFormsDisabled(false);
    if (job.status === 'succeeded') {
      setStatus('Completed', 'is-succeeded');
    } else {
      setStatus(`Failed${job.error ? `: ${job.error}` : ''}`, 'is-failed');
    }
  } catch (error) {
    setFormsDisabled(false);
    setStatus(`Error: ${error.message}`, 'is-failed');
  }
}

async function startJob(tool, payload) {
  stopPolling();
  setFormsDisabled(true);
  setStatus('Submitting...', 'is-running');
  setLogText('Submitting job...');
  renderArtifacts('', []);

  try {
    const response = await fetch(apiUrl(`/api/run/${tool}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }

    activeJobId = data.job_id;
    setStatus('Queued', 'is-running');
    pollJob(activeJobId);
  } catch (error) {
    setFormsDisabled(false);
    setStatus(`Error: ${error.message}`, 'is-failed');
    setLogText(String(error.message || error));
  }
}

function activateTool(toolName) {
  tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.tool === toolName));
  panels.forEach((panel) => panel.classList.toggle('active', panel.dataset.panel === toolName));
}

tabs.forEach((tab) => {
  tab.addEventListener('click', () => activateTool(tab.dataset.tool));
});

function bindForm(formId, toolName) {
  const form = document.getElementById(formId);
  if (!form) return;

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {};
    for (const [key, value] of formData.entries()) {
      payload[key] = String(value).trim();
    }
    startJob(toolName, payload);
  });
}

bindForm('form-deep-dive', 'competitive-deep-dive');
bindForm('form-positioning', 'protocol-positioning');

const presetTool = new URLSearchParams(window.location.search).get('tool');
if (presetTool && tabs.some((tab) => tab.dataset.tool === presetTool)) {
  activateTool(presetTool);
}

setStatus('Idle');
