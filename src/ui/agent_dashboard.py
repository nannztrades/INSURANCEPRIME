
# src/ui/agent_dashboard.py
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui/agent", tags=["Agent Dashboard"])

_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Agent Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 0; }
  header { padding: 16px 20px; background: #1f2937; color: #fff; }
  header h1 { margin: 0; font-size: 20px; }
  header p { margin: 4px 0 0 0; opacity: .9; }
  main { padding: 16px 20px 60px; }
  .panel { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0; background: #fff; }
  .panel h2 { margin: 0 0 12px 0; font-size: 16px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .row > * { margin: 4px 0; }
  label { font-weight: 600; margin-right: 6px; }
  input[type=text], select { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; min-width: 220px; }
  button { padding: 8px 12px; border: 1px solid #374151; background: #111827; color: #fff; border-radius: 6px; cursor: pointer; }
  button.secondary { background: #fff; color: #111827; border-color: #6b7280; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .hint { font-size: 12px; opacity: .8; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; font-size: 14px; white-space: nowrap; }
  th { background: #f9fafb; }
  .ok { color: #047857; }
  .bad { color: #b91c1c; }
  .muted { opacity: .75; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #f3f4f6; }
  .grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
  @media (max-width: 880px) { .grid-2 { grid-template-columns: 1fr; } }
  .fade { animation: fade .25s ease-in; }
  @keyframes fade { from {opacity: 0} to {opacity: 1} }
  .small { font-size: 12px; }
  a.button-link { text-decoration: none; display: inline-block; padding: 8px 12px; border: 1px solid #374151; background: #fff; color: #111827; border-radius: 6px; }
</style>
</head>
<body>
<header>
  <h1 id="title">Agent Dashboard</h1>
  <p id="subtitle" class="muted">Signed in as: <span id="who"></span></p>
</header>

<main>

  <div class="panel">
    <div class="row">
      <label for="month">Month (e.g., <span class="pill">Jun 2025</span> or <span class="pill">2025-06</span>):</label>
      <input id="month" type="text" placeholder="Jun 2025" />
      <button onclick="loadSummary()">Summary</button>
      <span id="sum_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody id="sum_tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="grid-2">

    <div class="panel">
      <h2>Statements</h2>
      <div class="row">
        <button onclick="loadStatements()">Load</button>
        <a id="st_csv" class="button-link" href="#" target="_blank" rel="noopener">CSV</a>
        <span id="st_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Policy</th>
              <th>Holder</th>
              <th>Type</th>
              <th>Pay Date</th>
              <th>Premium</th>
              <th>Com %</th>
              <th>Com Amt</th>
              <th>Month</th>
            </tr>
          </thead>
          <tbody id="st_tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Schedule (Latest per Month)</h2>
      <div class="row">
        <label>Latest-only</label>
        <button onclick="loadSchedule(true)">Load</button>
        <a id="sc_csv" class="button-link" href="#" target="_blank" rel="noopener">CSV</a>
        <span id="sc_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Schedule ID</th>
              <th>Upload</th>
              <th>Agent</th>
              <th>Name</th>
              <th>Batch</th>
              <th>Total Premiums</th>
              <th>Income</th>
              <th>Total Deductions</th>
              <th>Net Commission</th>
              <th>Month</th>
            </tr>
          </thead>
          <tbody id="sc_tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Terminated</h2>
      <div class="row">
        <input id="te_pol" type="text" placeholder="Policy No (optional)" />
        <button onclick="loadTerminated()">Load</button>
        <a id="te_csv" class="button-link" href="#" target="_blank" rel="noopener">CSV</a>
        <span id="te_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Upload</th>
              <th>Agent</th>
              <th>Policy</th>
              <th>Holder</th>
              <th>Type</th>
              <th>Premium</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Month</th>
              <th>Termination Date</th>
            </tr>
          </thead>
          <tbody id="te_tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Active Policies</h2>
      <div class="row">
        <label for="ap_status">Status</label>
        <select id="ap_status">
          <option value="">(any)</option>
          <option value="ACTIVE">ACTIVE</option>
          <option value="MISSING">MISSING</option>
        </select>
        <button onclick="loadActive()">Load</button>
        <a id="ap_csv" class="button-link" href="#" target="_blank" rel="noopener">CSV</a>
        <span id="ap_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Agent</th>
              <th>Policy</th>
              <th>Type</th>
              <th>Holder</th>
              <th>Inception</th>
              <th>First Seen</th>
              <th>Last Seen</th>
              <th>Seen Month</th>
              <th>Last Premium</th>
              <th>Last Com %</th>
              <th>Status</th>
              <th>Consecutive Missing</th>
            </tr>
          </thead>
          <tbody id="ap_tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="panel">
      <h2>Missing (Active-as-of minus Statements-In-Month)</h2>
      <div class="row">
        <button onclick="loadMissing()">Load</button>
        <span id="mi_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Policy</th>
              <th>Last Seen Month</th>
              <th>Last Premium</th>
            </tr>
          </thead>
          <tbody id="mi_tbody"></tbody>
        </table>
      </div>
      <p class="small muted">Definition: a policy counted ACTIVE on/before the month and not terminated on/before the month but absent from the month’s statement.</p>
    </div>

    <div class="panel">
      <h2>Uploads Tracker (Last N Months)</h2>
      <div class="row">
        <label>Months back</label>
        <input id="ut_back" type="text" value="36" style="width: 80px;" />
        <button onclick="loadUploadsTracker()">Load</button>
        <a id="ut_csv" class="button-link" href="#" target="_blank" rel="noopener">CSV</a>
        <span id="ut_info" class="hint"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Month</th>
              <th>Statement?</th>
              <th>Schedule?</th>
              <th>Terminated?</th>
              <th>Statement UploadID</th>
              <th>Schedule UploadID</th>
              <th>Terminated UploadID</th>
            </tr>
          </thead>
          <tbody id="ut_tbody"></tbody>
        </table>
      </div>
    </div>

  </div>
</main>

<script>
  // Small helpers
  const $ = (id) => document.getElementById(id);
  const text = (id, v) => { const el = $(id); if (el) el.textContent = v ?? ""; };
  const html = (id, v) => { const el = $(id); if (el) el.innerHTML = v ?? ""; };
  const val = (id) => (($(id) || {}).value || "").trim();
  const clearBody = (id) => { const b = $(id); if (b) b.innerHTML = ""; }
  const appendRow = (id, rowHTML) => { const b = $(id); if (!b) return; const tr = document.createElement('tr'); tr.className='fade'; tr.innerHTML = rowHTML; b.appendChild(tr); };

  // Identity
  let IDENTITY = { role: '', agent_code: '', agent_name: '' };

  async function whoAmI() {
    try {
      const r = await fetch('/api/auth/me', { credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.status !== 'OK') {
        text('who', 'Anonymous');
        return;
      }
      const id = j.identity || {};
      IDENTITY.role = id.role ?? '';
      IDENTITY.agent_code = id.agent_code ?? '';
      IDENTITY.agent_name = id.agent_name ?? id.agent_code ?? ''; // uses `agent_name` claim
      text('who', `${IDENTITY.agent_name} (${IDENTITY.agent_code})`);
      text('title', `Agent Dashboard — ${IDENTITY.agent_name}`);
      text('subtitle', `Signed in as: ${IDENTITY.agent_name} (${IDENTITY.agent_code})`);
    } catch (e) {
      text('who', 'Error determining identity');
    }
  }

  function ensureAgent() {
    if (!IDENTITY.agent_code) {
      alert('Please sign in as an agent first.');
      return false;
    }
    return true;
  }

  // Summary (policy counts by type, total active)
  async function loadSummary() {
    if (!ensureAgent()) return;
    const month = val('month');
    text('sum_info', 'Loading…');
    clearBody('sum_tbody');
    try {
      const q = new URLSearchParams({ agent_code: IDENTITY.agent_code });
      if (month) q.append('month_year', month);
      const r = await fetch(`/api/agent/summary?${q.toString()}`, { credentials: 'same-origin' });
      const j = await r.json();
      if (!r.ok) { text('sum_info', j.detail ?? 'Failed'); return; }
      appendRow('sum_tbody', `<td>Agent Code</td><td>${j.agent_code ?? ''}</td>`);
      appendRow('sum_tbody', `<td>Month</td><td>${j.month_year ?? ''}</td>`);
      appendRow('sum_tbody', `<td>Active policies total</td><td>${j.active_policies_total ?? 0}</td>`);
      const pt = j.policy_type_counts || {};
      Object.keys(pt).sort().forEach(k => {
        appendRow('sum_tbody', `<td>Type — ${k}</td><td>${pt[k]}</td>`);
      });
      text('sum_info', 'Done');
    } catch (e) {
      text('sum_info', String(e));
    }
  }

  // Statements
  async function loadStatements() {
    if (!ensureAgent()) return;
    const month = val('month');
    text('st_info', 'Loading…');
    clearBody('st_tbody');
    try {
      const q = new URLSearchParams();
      if (month) q.append('month_year', month);
      const url = `/api/agent/statements?${q.toString()}`;
      const csv = `/api/agent/statements.csv?${q.toString()}`;
      $('st_csv').href = csv;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(s => {
        appendRow('st_tbody',
          `<td>${s.statement_id ?? ''}</td><td>${s.policy_no ?? ''}</td><td>${s.holder ?? ''}</td>
           <td>${s.policy_type ?? ''}</td><td>${s.pay_date ?? ''}</td><td>${s.premium ?? ''}</td>
           <td>${s.com_rate ?? ''}</td><td>${s.com_amt ?? ''}</td><td>${s.month_year ?? ''}</td>`);
      });
      text('st_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('st_info', String(e));
    }
  }

  // Schedule
  async function loadSchedule(latest=true) {
    if (!ensureAgent()) return;
    const month = val('month');
    text('sc_info', 'Loading…');
    clearBody('sc_tbody');
    try {
      const q = new URLSearchParams();
      if (month) q.append('month_year', month);
      if (latest) q.append('latest_only', '1');
      const url = `/api/agent/schedule?${q.toString()}`;
      const csv = `/api/agent/schedule.csv?${q.toString()}`;
      $('sc_csv').href = csv;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(sc => {
        appendRow('sc_tbody',
          `<td>${sc.schedule_id ?? ''}</td><td>${sc.upload_id ?? ''}</td><td>${sc.agent_code ?? ''}</td>
           <td>${sc.agent_name ?? ''}</td><td>${sc.commission_batch_code ?? ''}</td>
           <td>${sc.total_premiums ?? ''}</td><td>${sc.income ?? ''}</td>
           <td>${sc.total_deductions ?? ''}</td><td>${sc.net_commission ?? ''}</td>
           <td>${sc.month_year ?? ''}</td>`);
      });
      text('sc_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('sc_info', String(e));
    }
  }

  // Terminated
  async function loadTerminated() {
    if (!ensureAgent()) return;
    const month = val('month');
    const pol = val('te_pol');
    text('te_info', 'Loading…');
    clearBody('te_tbody');
    try {
      const q = new URLSearchParams();
      if (month) q.append('month_year', month);
      if (pol) q.append('policy_no', pol);
      const url = `/api/agent/terminated?${q.toString()}`;
      const csv = `/api/agent/terminated.csv?${q.toString()}`;
      $('te_csv').href = csv;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(t => {
        appendRow('te_tbody',
          `<td>${t.terminated_id ?? ''}</td><td>${t.upload_id ?? ''}</td><td>${t.agent_code ?? ''}</td>
           <td>${t.policy_no ?? ''}</td><td>${t.holder ?? ''}</td><td>${t.policy_type ?? ''}</td>
           <td>${t.premium ?? ''}</td><td>${t.status ?? ''}</td><td>${t.reason ?? ''}</td>
           <td>${t.month_year ?? ''}</td><td>${t.termination_date ?? ''}</td>`);
      });
      text('te_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('te_info', String(e));
    }
  }

  // Active policies
  async function loadActive() {
    if (!ensureAgent()) return;
    const month = val('month');
    const status = val('ap_status');
    text('ap_info', 'Loading…');
    clearBody('ap_tbody');
    try {
      const q = new URLSearchParams();
      if (month) q.append('month_year', month);
      if (status) q.append('status', status);
      const url = `/api/agent/active-policies?${q.toString()}`;
      const csv = `/api/admin/active-policies.csv?${new URLSearchParams({agent_code: IDENTITY.agent_code, month_year: month, status}).toString()}`;
      $('ap_csv').href = csv;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(x => {
        appendRow('ap_tbody',
          `<td>${x.id ?? ''}</td><td>${x.agent_code ?? ''}</td><td>${x.policy_no ?? ''}</td>
           <td>${x.policy_type ?? ''}</td><td>${x.holder_name ?? ''}</td><td>${x.inception_date ?? ''}</td>
           <td>${x.first_seen_date ?? ''}</td><td>${x.last_seen_date ?? ''}</td><td>${x.last_seen_month_year ?? ''}</td>
           <td>${x.last_premium ?? ''}</td><td>${x.last_com_rate ?? ''}</td><td>${x.status ?? ''}</td>
           <td>${x.consecutive_missing_months ?? ''}</td>`);
      });
      text('ap_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('ap_info', String(e));
    }
  }

  // Missing
  async function loadMissing() {
    if (!ensureAgent()) return;
    const month = val('month');
    if (!month) { alert('Enter a month (e.g., Jun 2025)'); return; }
    text('mi_info', 'Loading…');
    clearBody('mi_tbody');
    try {
      const url = `/api/agent/missing?${new URLSearchParams({ month_year: month }).toString()}`;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(m => {
        appendRow('mi_tbody',
          `<td>${m.policy_no ?? ''}</td><td>${m.last_seen_month ?? ''}</td><td>${m.last_premium ?? ''}</td>`);
      });
      text('mi_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('mi_info', String(e));
    }
  }

  // Uploads tracker
  async function loadUploadsTracker() {
    if (!ensureAgent()) return;
    const back = (val('ut_back') || '36');
    text('ut_info', 'Loading…');
    clearBody('ut_tbody');
    try {
      const url = `/api/agent/uploads/tracker?${new URLSearchParams({ months_back: back }).toString()}`;
      const csv = `/api/admin/uploads.csv?${new URLSearchParams({agent_code: IDENTITY.agent_code}).toString()}`;
      $('ut_csv').href = csv;
      const r = await fetch(url, { credentials: 'same-origin' });
      const j = await r.json();
      (j.items ?? []).forEach(u => {
        const yesNo = (v) => (v ? '<span class="ok">YES</span>' : '<span class="bad">NO</span>');
        appendRow('ut_tbody',
          `<td>${u.month_year ?? ''}</td><td>${yesNo(u.statement_present)}</td><td>${yesNo(u.schedule_present)}</td>
           <td>${yesNo(u.terminated_present)}</td><td>${u.statement_upload_id ?? ''}</td>
           <td>${u.schedule_upload_id ?? ''}</td><td>${u.terminated_upload_id ?? ''}</td>`);
      });
      text('ut_info', `Items: ${j.count ?? 0}`);
    } catch (e) {
      text('ut_info', String(e));
    }
  }

  // Initial load
  whoAmI();
</script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
async def agent_dashboard() -> HTMLResponse:
    return HTMLResponse(_PAGE)
