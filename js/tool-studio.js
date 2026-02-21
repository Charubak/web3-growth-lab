const tabs = Array.from(document.querySelectorAll('.tool-tab'));
const panels = Array.from(document.querySelectorAll('.tool-panel'));
const statusEl = document.getElementById('job-status');
const terminalEl = document.getElementById('terminal-log');
const artifactListEl = document.getElementById('artifact-list');
const PROD_API_ORIGIN = 'https://api.web3growthlab.com';
const BACKUP_API_ORIGIN = 'https://web3growthlab-api.fly.dev';

function resolveApiOrigin() {
  const params = new URLSearchParams(window.location.search);
  const override = (params.get('api') || '').trim();
  if (override) return override.replace(/\/+$/, '');

  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') {
    return `${window.location.protocol}//${host}:8450`;
  }

  if (host === 'api.web3growthlab.com') {
    return window.location.origin;
  }

  return PROD_API_ORIGIN;
}

const apiOrigin = resolveApiOrigin();
let activeApiOrigin = apiOrigin;
const params = new URLSearchParams(window.location.search);
const urlKey = (params.get('key') || '').trim();
if (urlKey) {
  localStorage.setItem('toolStudioApiKey', urlKey);
}
const toolStudioApiKey = localStorage.getItem('toolStudioApiKey') || '';

let activeJobId = null;
let pollTimer = null;

function apiUrl(path) {
  return `${activeApiOrigin}${path}`;
}

function authHeaders(base = {}) {
  const headers = { ...base };
  if (toolStudioApiKey) {
    headers['X-Tool-Studio-Key'] = toolStudioApiKey;
  }
  return headers;
}

async function apiFetch(path, options = {}) {
  try {
    return await fetch(apiUrl(path), options);
  } catch (error) {
    if (activeApiOrigin === PROD_API_ORIGIN) {
      activeApiOrigin = BACKUP_API_ORIGIN;
      return fetch(apiUrl(path), options);
    }
    throw error;
  }
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
    const response = await apiFetch(`/api/jobs/${jobId}`, {
      cache: 'no-store',
      headers: authHeaders(),
    });
    if (!response.ok) {
      if ((response.status === 404 || response.status === 425) && jobId) {
        // Some backends return accepted before the job row is queryable.
        setStatus('Queued', 'is-running');
        pollTimer = setTimeout(() => pollJob(jobId), 1250);
        return;
      }
      throw new Error(`Job fetch failed (${response.status})`);
    }

    const job = await response.json();
    const logs = Array.isArray(job.logs)
      ? job.logs.join('\n')
      : typeof job.logs === 'string'
        ? job.logs
        : '';
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
    const response = await apiFetch(`/api/run/${tool}`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });

    const responseText = await response.text();
    let data = {};
    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch {
        data = {};
      }
    }
    if (!response.ok) {
      throw new Error(data.error || `Request failed (${response.status})`);
    }

    activeJobId = data.job_id || data.jobId || data.id || data?.job?.id || null;
    if (!activeJobId) {
      throw new Error(`Accepted but no job id returned (${response.status})`);
    }

    const accepted = response.status === 201 || response.status === 202;
    setStatus(accepted ? 'Accepted' : 'Queued', 'is-running');
    setLogText(
      accepted
        ? 'Request accepted. Waiting for worker...'
        : 'Job queued. Waiting for worker...'
    );
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
