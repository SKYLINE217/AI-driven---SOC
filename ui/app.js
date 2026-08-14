// ui/app.js — SOC Triager Desktop
// Single-page Vanilla JS application (ported from SOC_Dashboard.jsx)
'use strict';

// ── Mermaid init ──────────────────────────────────────────────────────────────
if (typeof mermaid !== 'undefined') {
  mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
}

// ── Global state ──────────────────────────────────────────────────────────────
const STATE = {
  page: 'alerts',
  role: 'analyst',
  incidents: [],
  alerts: [],
  stats: {},
  rules: [],
  selectedIncident: null,
  detailTab: 'overview',
  alertFilter: 'all',
  tablePage: 0,
  newAlertCount: 0,
  tickerMessages: [],
  mitreFilter: null,
  chartInstances: {},
};

// ── Utility helpers ───────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = (Date.now() - new Date(isoStr)) / 1000;
  if (diff < 60)    return `${Math.round(diff)}s ago`;
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function fmtTs(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleString();
}

function scoreColor(s) {
  if (s >= 0.75) return '#ef4444';
  if (s >= 0.50) return '#f97316';
  if (s >= 0.30) return '#eab308';
  return '#22c55e';
}

// ── Small component functions ─────────────────────────────────────────────────

function renderSevBadge(sev) {
  const s = (sev || 'unknown').toLowerCase();
  const dot = { critical: '●', high: '●', medium: '●', low: '●' }[s] || '●';
  return `<span class="sev-badge sev-${s}">${dot} ${s.charAt(0).toUpperCase() + s.slice(1)}</span>`;
}

function renderStatusBadge(status) {
  const s = (status || 'open').toLowerCase();
  const labels = {
    open: 'Open',
    investigating: 'Investigating',
    resolved: 'Resolved',
    false_positive: 'False Positive',
  };
  return `<span class="status-badge status-${s}">${labels[s] || s}</span>`;
}

function renderTechChip(id, tactic) {
  if (!id) return '<span style="color:var(--text-secondary)">—</span>';
  const title = tactic ? `title="${escHtml(tactic)}"` : '';
  return `<span class="tech-chip" ${title}>${escHtml(id)}</span>`;
}

function renderScoreBar(score) {
  const pct = Math.round((score || 0) * 100);
  return `
    <div class="score-bar-wrap">
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width:${pct}%;background:${scoreColor(score)};"></div>
      </div>
      <span class="score-val">${(score || 0).toFixed(2)}</span>
    </div>`;
}

function renderStatCard(value, label, color) {
  const col = color ? `color:${color}` : '';
  return `
    <div class="stat-card">
      <div class="stat-number" style="${col}">${value ?? '—'}</div>
      <div class="stat-label">${label}</div>
    </div>`;
}

// ── MITRE Matrix data ─────────────────────────────────────────────────────────

const MITRE_MATRIX = [
  { tactic: 'Initial Access',       techniques: ['T1078', 'T1190', 'T1566'] },
  { tactic: 'Execution',            techniques: ['T1059', 'T1203', 'T1106'] },
  { tactic: 'Persistence',          techniques: ['T1098', 'T1136', 'T1547'] },
  { tactic: 'Privilege Escalation', techniques: ['T1548', 'T1068', 'T1134'] },
  { tactic: 'Defense Evasion',      techniques: ['T1055', 'T1070', 'T1140'] },
  { tactic: 'Credential Access',    techniques: ['T1110', 'T1003', 'T1110.001'] },
  { tactic: 'Discovery',            techniques: ['T1046', 'T1083', 'T1057'] },
  { tactic: 'Lateral Movement',     techniques: ['T1021', 'T1021.001', 'T1021.002', 'T1021.004'] },
  { tactic: 'Collection',           techniques: ['T1005', 'T1025', 'T1074'] },
  { tactic: 'Exfiltration',         techniques: ['T1041', 'T1048', 'T1052'] },
  { tactic: 'Impact',               techniques: ['T1498', 'T1486', 'T1499'] },
];

function getHeatCount(tech) {
  return STATE.incidents.filter(i => i.technique === tech || (i.technique || '').startsWith(tech + '.')).length;
}

function heatColor(c) {
  if (c === 0) return 'var(--surface-1)';
  if (c === 1) return '#fef3c7';
  if (c === 2) return '#fed7aa';
  return '#fca5a5';
}

// ── Playbook catalog ──────────────────────────────────────────────────────────

const PLAYBOOK_CATALOG = [
  {
    id: 'PB-001',
    name: 'Credential Stuffing Response',
    technique: 'T1110',
    tactic: 'Credential Access',
    ioc_vars: ['src_ip', 'target_account', 'auth_threshold'],
    steps: ['Block source IP at perimeter firewall', 'Force password reset on targeted account', 'Enable MFA if not already active', 'Review auth logs for last 24h', 'Notify account owner'],
  },
  {
    id: 'PB-002',
    name: 'Lateral Movement Containment',
    technique: 'T1021',
    tactic: 'Lateral Movement',
    ioc_vars: ['src_host', 'dst_host', 'protocol'],
    steps: ['Isolate source host from network segment', 'Block RDP/SMB between affected subnets', 'Collect memory dump from source host', 'Review AD event logs for pass-the-hash', 'Escalate to IR team'],
  },
  {
    id: 'PB-003',
    name: 'Exfiltration Blocking',
    technique: 'T1041',
    tactic: 'Exfiltration',
    ioc_vars: ['dst_ip', 'dst_port', 'bytes_transferred'],
    steps: ['Block outbound connection to dst_ip on perimeter', 'Capture PCAP from affected endpoint', 'Identify and quarantine originating process', 'Notify DLP team', 'File IR ticket'],
  },
  {
    id: 'PB-004',
    name: 'Ransomware Triage',
    technique: 'T1486',
    tactic: 'Impact',
    ioc_vars: ['entity', 'encrypted_extensions', 'ransom_note_path'],
    steps: ['Immediately isolate affected host from network', 'Disable mapped network drives on segment', 'Preserve disk image before any remediation', 'Identify patient-zero via EDR telemetry', 'Engage ransomware response retainer'],
  },
  {
    id: 'PB-005',
    name: 'Privilege Escalation Response',
    technique: 'T1548',
    tactic: 'Privilege Escalation',
    ioc_vars: ['entity', 'escalated_account', 'method'],
    steps: ['Revoke elevated privileges immediately', 'Lock compromised account', 'Review sudo / UAC logs', 'Check for persistence mechanisms (T1547)', 'Escalate to tier-3 analyst'],
  },
];

// ── Data generators (for Ops charts — simulated) ──────────────────────────────

function genThroughput() {
  const now = Date.now();
  return Array.from({ length: 60 }, (_, i) => ({
    t: new Date(now - (59 - i) * 60000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    v: Math.floor(80 + Math.random() * 120 + (i > 40 ? 60 : 0)),
  }));
}

function genAlertVolume() {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return days.map(d => ({ day: d, count: Math.floor(20 + Math.random() * 80) }));
}

function genLatency() {
  const now = Date.now();
  return Array.from({ length: 30 }, (_, i) => ({
    t: new Date(now - (29 - i) * 3600000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    p50: Math.round(1200 + Math.random() * 800),
    p95: Math.round(3500 + Math.random() * 2000),
  }));
}

function generateScoreDistribution() {
  const buckets = ['0.0–0.2', '0.2–0.4', '0.4–0.6', '0.6–0.8', '0.8–1.0'];
  return buckets.map(b => ({ bucket: b, count: Math.floor(5 + Math.random() * 40) }));
}

// ── Playbook YAML generator ───────────────────────────────────────────────────

function genPlaybook(inc) {
  return `---
# SOC Containment Playbook — DRAFT
# Incident: ${inc.id}
# Technique: ${inc.technique || 'N/A'} (${inc.tactic || 'N/A'})
# Generated: ${new Date().toISOString()}
# WARNING: DRAFT ONLY — Requires Approver authorization before execution.

- name: SOC Containment for ${escHtml(inc.entity)}
  hosts: "{{ target_host | default('${escHtml(inc.entity)}') }}"
  gather_facts: false
  vars:
    incident_id: "${inc.id}"
    technique:   "${inc.technique || 'N/A'}"
    severity:    "${inc.severity || 'N/A'}"
    analyst:     "${STATE.role}"

  tasks:
    - name: Notify SOC channel
      uri:
        url: "{{ slack_webhook }}"
        method: POST
        body_format: json
        body:
          text: "🚨 Incident {{ incident_id }} — {{ technique }} on {{ inventory_hostname }}"

    - name: Isolate host from network (firewall rule)
      iptables:
        chain: INPUT
        source: "{{ inventory_hostname }}"
        jump: DROP
      when: severity in ['critical', 'high']

    - name: Capture running process list
      command: ps aux
      register: process_snapshot

    - name: Save process snapshot as artifact
      copy:
        content: "{{ process_snapshot.stdout }}"
        dest: "/tmp/soc_{{ incident_id }}_processes.txt"

    - name: Update incident status via SOC API
      uri:
        url: "http://127.0.0.1:8765/api/incidents/{{ incident_id }}/status"
        method: POST
        body_format: json
        body:
          status: investigating
          actor: "{{ analyst }}"
`;
}

// ── Mermaid graph generator ───────────────────────────────────────────────────

function genMermaidGraph(inc) {
  const eid = (inc.entity || 'entity').replace(/[^a-zA-Z0-9_]/g, '_');
  const tid = (inc.technique || 'T????').replace('.', '_');
  return `graph LR
  A["🖥️ ${escHtml(inc.entity)}"]:::entity
  B["🔍 Detection\\n${escHtml(inc.technique || '')}"]:::detection
  C["⚠️ Incident\\n${escHtml(inc.severity || '')} severity"]:::incident
  D["${escHtml(inc.tactic || 'Unknown Tactic')}"]:::tactic

  A -->|anomaly score ${(inc.confidence || 0).toFixed(2)}| B
  B --> C
  C --> D

  classDef entity    fill:#eff6ff,stroke:#2a78d6,color:#1e3a8a
  classDef detection fill:#fef3c7,stroke:#d97706,color:#92400e
  classDef incident  fill:#fef2f2,stroke:#ef4444,color:#991b1b
  classDef tactic    fill:#f0fdf4,stroke:#22c55e,color:#166534
`;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function api(path, opts) {
  const res = await fetch('/api' + path, opts);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

async function loadData() {
  try {
    const [incidents, stats, rules] = await Promise.all([
      api('/incidents?limit=200'),
      api('/stats'),
      api('/rules'),
    ]);
    STATE.incidents = incidents || [];
    STATE.stats = stats || {};
    STATE.rules = Array.isArray(rules) ? rules : [];
  } catch (e) {
    console.error('loadData error:', e);
  }
}

async function updateStatus(incidentId, newStatus) {
  try {
    await api(`/incidents/${incidentId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, actor: STATE.role }),
    });
    await loadData();
    if (STATE.selectedIncident && STATE.selectedIncident.id === incidentId) {
      STATE.selectedIncident = await api(`/incidents/${incidentId}`);
    }
    render();
  } catch (e) {
    alert(`Failed to update status: ${e.message}`);
  }
}

async function openDetail(incidentId) {
  try {
    const inc = await api(`/incidents/${incidentId}`);
    STATE.selectedIncident = inc;
    STATE.detailTab = 'overview';
    render();
  } catch (e) {
    console.error('openDetail error:', e);
  }
}

// ── Sidebar renderer ──────────────────────────────────────────────────────────

function renderSidebar() {
  const pages = [
    { id: 'alerts',    icon: '🔔', label: 'Alert Queue' },
    { id: 'incidents', icon: '📋', label: 'Incidents' },
    { id: 'navigator', icon: '🗺️',  label: 'MITRE Navigator' },
    { id: 'ops',       icon: '📊', label: 'Ops Metrics' },
    { id: 'playbooks', icon: '📖', label: 'Playbooks' },
    { id: 'rules',     icon: '⚙️',  label: 'Detection Rules' },
  ];

  const badge = STATE.newAlertCount > 0
    ? `<span class="badge">${STATE.newAlertCount}</span>` : '';

  return `
    <div class="nav-logo">🛡 SOC Triager</div>
    <div class="nav-section">Navigation</div>
    ${pages.map(p => `
      <button id="nav-${p.id}" class="nav-btn ${STATE.page === p.id ? 'active' : ''}"
              onclick="navigateTo('${p.id}')">
        <span class="nav-icon">${p.icon}</span>
        ${p.label}
        ${p.id === 'alerts' ? badge : ''}
      </button>`).join('')}
    <div class="nav-footer">
      Role: <strong>${STATE.role}</strong><br>
      DB: SQLite · API: :8765
    </div>`;
}

// ── Page: Alert Queue ─────────────────────────────────────────────────────────

function renderAlertsPage() {
  const s = STATE.stats;
  const filtered = STATE.alertFilter === 'all'
    ? STATE.incidents
    : STATE.incidents.filter(i => (i.severity || '').toLowerCase() === STATE.alertFilter);

  const ticker = STATE.tickerMessages.length > 0
    ? `<div class="ticker">
        <span class="ticker-label">LIVE</span>
        ${escHtml(STATE.tickerMessages.slice(-1)[0])}
       </div>` : '';

  return `
    ${ticker}
    <div class="page-header">
      <div>
        <div class="page-title">Alert Queue</div>
        <div class="page-sub">${STATE.incidents.length} incidents · last refreshed ${new Date().toLocaleTimeString()}</div>
      </div>
    </div>
    <div class="stat-grid">
      ${renderStatCard(s.total_incidents ?? 0, 'Total Incidents')}
      ${renderStatCard(s.critical_open ?? 0, 'Critical Open', '#ef4444')}
      ${renderStatCard(s.total_alerts ?? 0, 'Total Alerts')}
      ${renderStatCard((s.avg_anomaly_score ?? 0).toFixed(3), 'Avg Score')}
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <span class="filter-label">Filter:</span>
        ${['all', 'critical', 'high', 'medium', 'low'].map(f => `
          <button class="btn btn-sm ${STATE.alertFilter === f ? 'btn-primary' : ''}"
                  onclick="setState({alertFilter:'${f}',tablePage:0})">
            ${f.charAt(0).toUpperCase() + f.slice(1)}
          </button>`).join('')}
      </div>
      ${filtered.length === 0
        ? '<div class="empty">No incidents found.</div>'
        : `<table>
            <thead><tr>
              <th>Entity</th><th>Technique</th><th>Severity</th>
              <th>Status</th><th>Score</th><th>Alerts</th><th>Age</th><th></th>
            </tr></thead>
            <tbody>${renderIncidentRows(filtered)}</tbody>
           </table>`}
    </div>`;
}

function renderIncidentRows(rows) {
  const page = STATE.tablePage || 0;
  const pageSize = 50;
  const slice = rows.slice(page * pageSize, (page + 1) * pageSize);
  const pagination = rows.length > pageSize ? `
    <tr><td colspan="8">
      <div class="pagination">
        ${page > 0 ? `<button class="btn btn-sm" onclick="setState({tablePage:${page - 1}})">← Prev</button>` : ''}
        Page ${page + 1} / ${Math.ceil(rows.length / pageSize)}
        ${(page + 1) * pageSize < rows.length ? `<button class="btn btn-sm" onclick="setState({tablePage:${page + 1}})">Next →</button>` : ''}
      </div>
    </td></tr>` : '';
  return slice.map(inc => `
    <tr>
      <td><code style="font-size:11px">${escHtml(inc.entity)}</code></td>
      <td>${renderTechChip(inc.technique, inc.tactic)}</td>
      <td>${renderSevBadge(inc.severity)}</td>
      <td>${renderStatusBadge(inc.status)}</td>
      <td style="min-width:130px">${renderScoreBar(inc.confidence || 0)}</td>
      <td style="text-align:center">${inc.alert_count != null ? inc.alert_count : '—'}</td>
      <td style="color:var(--text-secondary)">${timeAgo(inc.created_at)}</td>
      <td><button class="btn btn-sm" onclick="openDetail('${escHtml(inc.id)}')">Open →</button></td>
    </tr>`).join('') + pagination;
}

// ── Page: Incidents ───────────────────────────────────────────────────────────

function renderIncidentsPage() {
  return `
    <div class="page-header">
      <div>
        <div class="page-title">All Incidents</div>
        <div class="page-sub">${STATE.incidents.length} total</div>
      </div>
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <table>
        <thead><tr>
          <th>ID</th><th>Entity</th><th>Technique</th><th>Severity</th>
          <th>Status</th><th>Score</th><th>Created</th><th></th>
        </tr></thead>
        <tbody>
          ${STATE.incidents.length === 0
            ? '<tr><td colspan="8"><div class="empty">No incidents found.</div></td></tr>'
            : STATE.incidents.map(inc => `
              <tr>
                <td><code style="font-size:10px;color:var(--text-secondary)">${escHtml(inc.id.slice(0, 8))}…</code></td>
                <td><strong>${escHtml(inc.entity)}</strong></td>
                <td>${renderTechChip(inc.technique, inc.tactic)}</td>
                <td>${renderSevBadge(inc.severity)}</td>
                <td>${renderStatusBadge(inc.status)}</td>
                <td style="min-width:120px">${renderScoreBar(inc.confidence || 0)}</td>
                <td style="color:var(--text-secondary);font-size:11px">${fmtTs(inc.created_at)}</td>
                <td><button class="btn btn-sm" onclick="openDetail('${escHtml(inc.id)}')">Open →</button></td>
              </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// ── Page: MITRE Navigator ─────────────────────────────────────────────────────

function filterByTechnique(tech) {
  setState({ mitreFilter: STATE.mitreFilter === tech ? null : tech });
}

function renderNavigatorPage() {
  const maxTechs = Math.max(...MITRE_MATRIX.map(c => c.techniques.length));
  const filtered = STATE.mitreFilter
    ? STATE.incidents.filter(i => i.technique === STATE.mitreFilter || (i.technique || '').startsWith(STATE.mitreFilter + '.'))
    : [];

  return `
    <div class="page-header">
      <div>
        <div class="page-title">MITRE ATT&CK Navigator</div>
        <div class="page-sub">Click a cell to filter incidents</div>
      </div>
      ${STATE.mitreFilter ? `<button class="btn btn-sm" onclick="setState({mitreFilter:null})">✕ Clear Filter</button>` : ''}
    </div>
    <div class="card" style="padding:0;overflow-x:auto">
      <table style="border-collapse:separate;border-spacing:3px;padding:12px">
        <thead>
          <tr>
            ${MITRE_MATRIX.map(col =>
              `<th style="font-size:10px;padding:4px 6px;min-width:92px;white-space:nowrap">${col.tactic}</th>`
            ).join('')}
          </tr>
        </thead>
        <tbody>
          ${Array.from({ length: maxTechs }, (_, row) => `
            <tr>
              ${MITRE_MATRIX.map(col => {
                const tech = col.techniques[row];
                if (!tech) return '<td></td>';
                const count = getHeatCount(tech);
                const isActive = STATE.mitreFilter === tech;
                return `<td style="padding:2px">
                  <div class="mitre-cell"
                       style="background:${isActive ? '#bfdbfe' : heatColor(count)};
                              color:${count > 0 ? '#1e293b' : 'var(--text-secondary)'};
                              outline:${isActive ? '2px solid #2a78d6' : 'none'}"
                       onclick="filterByTechnique('${tech}')"
                       title="${tech} — ${count} incident(s)">
                    <span>${tech}</span>
                    ${count > 0 ? `<span style="font-weight:700">${count}</span>` : ''}
                  </div>
                </td>`;
              }).join('')}
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
    ${STATE.mitreFilter ? `
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">
          Incidents matching <span class="tech-chip">${escHtml(STATE.mitreFilter)}</span>
          — ${filtered.length} found
        </div>
        ${filtered.length === 0
          ? '<div class="empty">No incidents for this technique.</div>'
          : `<table>
              <thead><tr><th>Entity</th><th>Severity</th><th>Status</th><th>Age</th><th></th></tr></thead>
              <tbody>${filtered.map(inc => `
                <tr>
                  <td>${escHtml(inc.entity)}</td>
                  <td>${renderSevBadge(inc.severity)}</td>
                  <td>${renderStatusBadge(inc.status)}</td>
                  <td style="color:var(--text-secondary)">${timeAgo(inc.created_at)}</td>
                  <td><button class="btn btn-sm" onclick="openDetail('${escHtml(inc.id)}')">Open →</button></td>
                </tr>`).join('')}
              </tbody>
             </table>`}
      </div>` : ''}`;
}

// ── Page: Ops Metrics ─────────────────────────────────────────────────────────

function renderOpsPage() {
  const s = STATE.stats;
  return `
    <div class="page-header">
      <div class="page-title">Operations Metrics</div>
    </div>
    <div class="stat-grid" style="grid-template-columns:repeat(4,1fr)">
      ${renderStatCard(s.total_incidents ?? 0, 'Total Incidents')}
      ${renderStatCard(s.total_alerts ?? 0, 'Total Alerts')}
      ${renderStatCard(s.critical_open ?? 0, 'Critical Open', '#ef4444')}
      ${renderStatCard((s.avg_anomaly_score ?? 0).toFixed(3), 'Avg Anomaly Score')}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Event Throughput (last 60m)</div>
        <canvas id="chart-throughput" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Alert Volume (weekly)</div>
        <canvas id="chart-volume" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Triage Latency (ms)</div>
        <canvas id="chart-latency" height="160"></canvas>
      </div>
      <div class="card">
        <div style="font-weight:600;margin-bottom:12px">Anomaly Score Distribution</div>
        <canvas id="chart-scores" height="160"></canvas>
      </div>
    </div>
    <div class="card" style="margin-top:0">
      <div style="font-weight:600;margin-bottom:12px">By Severity</div>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        ${Object.entries(s.by_severity || {}).map(([k, v]) =>
          `<div>${renderSevBadge(k)} <strong style="margin-left:6px">${v}</strong></div>`
        ).join('')}
      </div>
    </div>`;
}

function initOpsCharts() {
  if (STATE.page !== 'ops') return;

  // Destroy existing chart instances to avoid canvas reuse error
  Object.values(STATE.chartInstances).forEach(c => { try { c.destroy(); } catch (_) {} });
  STATE.chartInstances = {};

  const baseOpts = {
    responsive: true,
    animation: false,
    plugins: { legend: { display: false } },
  };

  // Throughput
  const tp = genThroughput();
  const tpCtx = document.getElementById('chart-throughput');
  if (tpCtx) {
    STATE.chartInstances['throughput'] = new Chart(tpCtx, {
      type: 'line',
      data: {
        labels: tp.map(d => d.t),
        datasets: [{ label: 'Events/min', data: tp.map(d => d.v),
          fill: true, borderColor: '#2a78d6', backgroundColor: 'rgba(42,120,214,0.10)',
          tension: 0.3, pointRadius: 0 }],
      },
      options: { ...baseOpts, scales: { y: { beginAtZero: false } } },
    });
  }

  // Volume
  const vol = genAlertVolume();
  const volCtx = document.getElementById('chart-volume');
  if (volCtx) {
    STATE.chartInstances['volume'] = new Chart(volCtx, {
      type: 'bar',
      data: {
        labels: vol.map(d => d.day),
        datasets: [{ label: 'Alerts', data: vol.map(d => d.count),
          backgroundColor: 'rgba(42,120,214,0.65)', borderRadius: 4 }],
      },
      options: { ...baseOpts },
    });
  }

  // Latency
  const lat = genLatency();
  const latCtx = document.getElementById('chart-latency');
  if (latCtx) {
    STATE.chartInstances['latency'] = new Chart(latCtx, {
      type: 'line',
      data: {
        labels: lat.map(d => d.t),
        datasets: [
          { label: 'P50', data: lat.map(d => d.p50), borderColor: '#22c55e', tension: 0.3, pointRadius: 0 },
          { label: 'P95', data: lat.map(d => d.p95), borderColor: '#ef4444', tension: 0.3, pointRadius: 0, borderDash: [4, 3] },
        ],
      },
      options: { ...baseOpts, plugins: { legend: { display: true, position: 'bottom' } }, scales: { y: { beginAtZero: false } } },
    });
  }

  // Score distribution
  const sd = generateScoreDistribution();
  const sdCtx = document.getElementById('chart-scores');
  if (sdCtx) {
    STATE.chartInstances['scores'] = new Chart(sdCtx, {
      type: 'bar',
      data: {
        labels: sd.map(d => d.bucket),
        datasets: [{ label: 'Count', data: sd.map(d => d.count),
          backgroundColor: ['#22c55e', '#eab308', '#f97316', '#ef4444', '#991b1b'],
          borderRadius: 4 }],
      },
      options: { ...baseOpts },
    });
  }
}

// ── Page: Playbooks ───────────────────────────────────────────────────────────

function renderPlaybooksPage() {
  return `
    <div class="page-header">
      <div class="page-title">Playbook Library</div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px">
      ${PLAYBOOK_CATALOG.map(pb => `
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
            <div>
              <div style="font-weight:700;margin-bottom:4px">${escHtml(pb.name)}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap">
                ${renderTechChip(pb.technique, pb.tactic)}
                <span style="font-size:11px;color:var(--text-secondary)">${escHtml(pb.tactic)}</span>
              </div>
            </div>
            <code style="font-size:10px;color:var(--text-secondary)">${pb.id}</code>
          </div>
          <div style="margin-bottom:8px">
            <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:4px">IOC Variables</div>
            <div style="display:flex;gap:4px;flex-wrap:wrap">
              ${pb.ioc_vars.map(v => `<code style="background:var(--surface-1);padding:2px 6px;border-radius:4px;font-size:10px">${v}</code>`).join('')}
            </div>
          </div>
          <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">Steps</div>
          <ol style="padding-left:18px;font-size:12px;color:var(--text-primary)">
            ${pb.steps.map(s => `<li style="margin-bottom:3px">${escHtml(s)}</li>`).join('')}
          </ol>
        </div>`).join('')}
    </div>`;
}

// ── Page: Detection Rules ─────────────────────────────────────────────────────

function renderRulesPage() {
  const rules = STATE.rules;
  return `
    <div class="page-header">
      <div>
        <div class="page-title">Detection Rules</div>
        <div class="page-sub">${rules.length} rules loaded from mitre/rules.yaml</div>
      </div>
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      ${rules.length === 0
        ? '<div class="empty">No rules found. Check mitre/rules.yaml.</div>'
        : `<table>
            <thead><tr>
              <th>Rule ID</th><th>Technique</th><th>Name</th>
              <th>Tactic</th><th>Condition</th><th>Status</th>
            </tr></thead>
            <tbody>
              ${rules.map(r => `
                <tr class="${r.enabled === false ? 'rule-row-disabled' : ''}">
                  <td><code style="font-size:10px">${escHtml(r.rule_id || r.id || '—')}</code></td>
                  <td>${renderTechChip(r.technique_id || r.technique)}</td>
                  <td style="font-weight:500">${escHtml(r.name || '—')}</td>
                  <td style="color:var(--text-secondary);font-size:11px">${escHtml(r.tactic || '—')}</td>
                  <td><code style="font-size:10px;white-space:pre-wrap">${escHtml(r.condition || r.description || '—')}</code></td>
                  <td>
                    <span class="status-badge ${r.enabled === false ? 'status-false_positive' : 'status-open'}">
                      ${r.enabled === false ? 'Disabled' : 'Enabled'}
                    </span>
                  </td>
                </tr>`).join('')}
            </tbody>
           </table>`}
    </div>`;
}

// ── Detail overlay — 5 tabs ───────────────────────────────────────────────────

function renderDetailContent() {
  const inc = STATE.selectedIncident;
  if (!inc) return '';
  const tabs = [
    { id: 'overview', label: '📋 Overview' },
    { id: 'graph',    label: '🔗 Attack Graph' },
    { id: 'mitre',    label: '🗺️ MITRE' },
    { id: 'playbook', label: '📖 Playbook' },
    { id: 'ledger',   label: '🔐 Ledger' },
  ];

  let body = '';
  switch (STATE.detailTab) {
    case 'overview': body = renderOverviewTab(inc); break;
    case 'graph':    body = renderGraphTab(inc);    break;
    case 'mitre':    body = renderMitreTab(inc);    break;
    case 'playbook': body = renderPlaybookTab(inc); break;
    case 'ledger':   body = renderLedgerTab(inc);   break;
    default:         body = renderOverviewTab(inc);
  }

  return `
    <div class="overlay-header">
      <div>
        <div style="font-size:18px;font-weight:700">${escHtml(inc.entity)}</div>
        <div style="margin-top:4px;display:flex;gap:6px;align-items:center">
          ${renderTechChip(inc.technique, inc.tactic)}
          ${renderSevBadge(inc.severity)}
          ${renderStatusBadge(inc.status)}
        </div>
      </div>
      <button class="close-btn" onclick="closeDetail()">✕</button>
    </div>
    <div class="tabs">
      ${tabs.map(t => `
        <button class="tab-btn ${STATE.detailTab === t.id ? 'active' : ''}"
                onclick="setState({detailTab:'${t.id}'})">${t.label}</button>`).join('')}
    </div>
    <div id="tab-body">${body}</div>`;
}

function renderOverviewTab(inc) {
  const statuses = ['open', 'investigating', 'resolved', 'false_positive'];
  return `
    <div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px">Confidence Score</div>
          <div style="width:220px">${renderScoreBar(inc.confidence || 0)}</div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          ${statuses.map(s => `
            <button class="btn btn-sm ${inc.status === s ? 'btn-primary' : ''}"
                    onclick="updateStatus('${escHtml(inc.id)}','${s}')">
              ${s.replace('_', ' ')}
            </button>`).join('')}
        </div>
      </div>
    </div>
    ${inc.rationale ? `
      <div class="card" style="margin-bottom:12px">
        <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:4px">Rationale</div>
        <div style="font-size:12px">${escHtml(inc.rationale)}</div>
      </div>` : ''}
    ${inc.recommended_immediate_action ? `
      <div class="card" style="margin-bottom:12px;background:var(--bg-accent);border-color:#bfdbfe">
        <div style="font-size:11px;font-weight:600;color:var(--accent);margin-bottom:4px">Recommended Action</div>
        <div style="font-size:12px">${escHtml(inc.recommended_immediate_action)}</div>
      </div>` : ''}
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:10px 14px;border-bottom:1px solid var(--border);font-weight:600;font-size:12px">
        Alerts (${(inc.alerts || []).length})
      </div>
      ${(inc.alerts || []).length === 0
        ? '<div class="empty">No alerts linked to this incident.</div>'
        : `<table>
            <thead><tr><th>Source</th><th>Severity</th><th>Score</th><th>Status</th><th>Time</th></tr></thead>
            <tbody>
              ${(inc.alerts || []).map(a => `
                <tr>
                  <td style="font-size:11px;color:var(--text-secondary)">${escHtml(a.source_type || '—')}</td>
                  <td>${renderSevBadge(a.severity)}</td>
                  <td>${renderScoreBar(a.anomaly_score || 0)}</td>
                  <td>${renderStatusBadge(a.status)}</td>
                  <td style="font-size:11px;color:var(--text-secondary)">${timeAgo(a.created_at)}</td>
                </tr>`).join('')}
            </tbody>
           </table>`}
    </div>`;
}

function renderGraphTab(inc) {
  const graphSrc = genMermaidGraph(inc);
  // Use a unique id to avoid mermaid re-rendering stale content
  const mid = 'mermaid-' + Date.now();
  setTimeout(() => {
    const el = document.getElementById(mid);
    if (el && typeof mermaid !== 'undefined') {
      try { mermaid.init(undefined, el); } catch (_) {}
    }
  }, 100);
  return `
    <div class="mermaid-wrap">
      <div id="${mid}" class="mermaid">${escHtml(graphSrc)}</div>
    </div>
    <div style="margin-top:12px">
      <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:6px">Mermaid Source</div>
      <pre>${escHtml(graphSrc)}</pre>
    </div>`;
}

function renderMitreTab(inc) {
  const col = MITRE_MATRIX.find(c => c.techniques.some(t => t === inc.technique || (inc.technique || '').startsWith(t + '.')));
  return `
    <div class="card">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">Technique ID</div>
          <div style="font-weight:700;font-family:monospace">${escHtml(inc.technique || '—')}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">Tactic</div>
          <div style="font-weight:600">${escHtml(inc.tactic || '—')}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">Matrix Column</div>
          <div>${col ? escHtml(col.tactic) : '—'}</div>
        </div>
        <div>
          <div style="font-size:11px;color:var(--text-secondary);margin-bottom:2px">Confidence</div>
          <div style="width:160px">${renderScoreBar(inc.confidence || 0)}</div>
        </div>
      </div>
    </div>
    ${col ? `
      <div class="card">
        <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:8px">
          Techniques in ${escHtml(col.tactic)}
        </div>
        <div style="display:flex;flex-direction:column;gap:4px">
          ${col.techniques.map(t => {
            const active = t === inc.technique;
            const cnt = getHeatCount(t);
            return `<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;
                                border-radius:6px;background:${active ? 'var(--bg-accent)' : 'var(--surface-0)'}">
              <span class="tech-chip">${t}</span>
              ${active ? '<span style="font-size:11px;color:var(--accent);font-weight:600">← this incident</span>' : ''}
              ${cnt > 0 ? `<span style="margin-left:auto;font-size:11px;color:var(--text-secondary)">${cnt} incident(s)</span>` : ''}
            </div>`;
          }).join('')}
        </div>
      </div>` : ''}
    ${inc.rationale ? `
      <div class="card">
        <div style="font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:4px">Rationale</div>
        <div style="font-size:12px">${escHtml(inc.rationale)}</div>
      </div>` : ''}`;
}

function renderPlaybookTab(inc) {
  const yaml = genPlaybook(inc);
  const escaped = yaml.replace(/`/g, '\\`');
  return `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <strong>Containment Playbook — DRAFT</strong>
      <button class="btn btn-sm" onclick="navigator.clipboard.writeText(\`${escaped}\`).then(()=>this.textContent='Copied!').catch(()=>{})">
        📋 Copy YAML
      </button>
    </div>
    <div class="playbook-warn">
      ⚠️ DRAFT ONLY — Requires Approver authorization before execution.
    </div>
    <pre>${escHtml(yaml)}</pre>`;
}

function renderLedgerTab(inc) {
  const ledger = inc.ledger || [];
  return `
    <div style="margin-bottom:12px">
      <strong>Audit Ledger</strong>
      <span style="font-size:11px;color:var(--text-secondary);margin-left:8px">${ledger.length} entries · hash-chained SHA-256</span>
    </div>
    ${ledger.length === 0
      ? '<div class="empty">No ledger entries.</div>'
      : `<table>
          <thead><tr>
            <th>Seq</th><th>Action</th><th>Actor</th>
            <th>Timestamp</th><th>Hash</th><th>Valid</th>
          </tr></thead>
          <tbody>
            ${ledger.map(e => `
              <tr>
                <td style="color:var(--text-secondary)">#${e.id}</td>
                <td><code>${escHtml(e.action || '—')}</code></td>
                <td>${escHtml(e.actor || '—')}</td>
                <td style="font-size:11px;color:var(--text-secondary)">${(e.timestamp || '').slice(0, 19).replace('T', ' ')}</td>
                <td><code style="font-size:10px">${String(e.this_hash || '').slice(0, 12)}…</code></td>
                <td style="font-size:16px;color:${e.valid === false ? '#ef4444' : '#22c55e'}">
                  ${e.valid === false ? '✗' : '✓'}
                </td>
              </tr>`).join('')}
          </tbody>
         </table>`}`;
}

// ── Page router ───────────────────────────────────────────────────────────────

function renderPage() {
  switch (STATE.page) {
    case 'alerts':    return renderAlertsPage();
    case 'incidents': return renderIncidentsPage();
    case 'navigator': return renderNavigatorPage();
    case 'ops':       return renderOpsPage();
    case 'playbooks': return renderPlaybooksPage();
    case 'rules':     return renderRulesPage();
    default:          return renderAlertsPage();
  }
}

// ── Global render ─────────────────────────────────────────────────────────────

function setState(patch) {
  Object.assign(STATE, patch);
  render();
}

function navigateTo(page) {
  STATE.page = page;
  if (page === 'alerts') STATE.newAlertCount = 0;
  STATE.tablePage = 0;
  render();
}

function closeDetail() {
  STATE.selectedIncident = null;
  render();
}

function render() {
  const sidebar = document.getElementById('sidebar');
  const main    = document.getElementById('main-content');
  const overlay = document.getElementById('detail-overlay');

  if (sidebar) sidebar.innerHTML = renderSidebar();
  if (main)    main.innerHTML    = renderPage();

  if (STATE.selectedIncident) {
    overlay.style.display = 'block';
    overlay.innerHTML = renderDetailContent();
  } else {
    overlay.style.display = 'none';
  }

  // Init charts after DOM update
  if (STATE.page === 'ops') setTimeout(initOpsCharts, 0);
}

// ── SSE subscription ──────────────────────────────────────────────────────────

function subscribeToAlerts() {
  const es = new EventSource('/api/stream');
  es.onmessage = (e) => {
    try {
      const alert = JSON.parse(e.data);
      STATE.newAlertCount++;
      STATE.alerts.unshift(alert);
      STATE.tickerMessages.push(
        `NEW ALERT · ${alert.entity || '?'} · ${alert.severity || '?'} · score ${(alert.anomaly_score || 0).toFixed(3)}`
      );
      if (STATE.tickerMessages.length > 20) STATE.tickerMessages.shift();
      // Only re-render sidebar badge (cheap) unless on alert page
      const sidebar = document.getElementById('sidebar');
      if (sidebar) sidebar.innerHTML = renderSidebar();
      if (STATE.page === 'alerts') render();
    } catch (_) {}
  };
  es.onerror = () => {
    es.close();
    setTimeout(subscribeToAlerts, 3000); // reconnect on error
  };
}

// ── Boot ──────────────────────────────────────────────────────────────────────

(async function boot() {
  await loadData();
  render();
  subscribeToAlerts();

  // Refresh data every 30 seconds
  setInterval(async () => {
    await loadData();
    render();
  }, 30_000);
})();
