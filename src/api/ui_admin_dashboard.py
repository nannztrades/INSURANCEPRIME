
# src/api/ui_admin_dashboard.py
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["Admin UI"])

_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>ICRS — Admin Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; padding: 0; }
  header { padding: 16px 20px; background: #111827; color: #fff; }
  header h1 { margin: 0; font-size: 20px; }
  header p { margin: 4px 0 0 0; opacity: .9; }
  main { padding: 16px 20px 60px; }
  .panel { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 16px 0; background: #fff; }
  .panel h2 { margin: 0 0 12px 0; font-size: 16px; }
  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  label { font-weight: 600; }
  input[type=text], select { padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; min-width: 220px; }
  button { padding: 8px 12px; border: 1px solid #374151; background: #111827; color: #fff; border-radius: 6px; cursor: pointer; }
  button.secondary { background: #fff; color: #111827; border-color: #6b7280; }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .hint { font-size: 12px; opacity: .8; }
  .muted { opacity: .75; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #f3f4f6; }
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #f3f4f6; text-align: left; font-size: 14px; white-space: nowrap; }
  th { background: #f9fafb; }
  .grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
  @media (max-width: 980px) { .grid-2 { grid-template-columns: 1fr; } }
  .fade { animation: fade .25s ease-in; }
  @keyframes fade { from {opacity: 0} to {opacity: 1} }
  .small { font-size: 12px; }
  a.button-link { text-decoration: none; display: inline-block; padding: 8px 12px; border: 1px solid #374151; background: #fff; color: #111827; border-radius: 6px; }
  .ok { color: #047857; }
  .bad { color: #b91c1c; }
</style>
</head>
<body>
<header>
  <h1 id="title">ICRS — Admin Dashboard</h1>
  <p id="subtitle" class="muted">Signed in as: <span id="who"></span></p>
</header>

<main>

  <!-- Filters -->
  <div class="panel">
    <div class="row">
      <label for="f_agent">Agent</label>
      <input id="f_agent" type="text" placeholder="9518" />
      <label for="f_month">Month</label>
      <input id="f_month" type="text" placeholder="Jun 2025 or 2025-06" />
      <button onclick="whoAmI()" class="secondary">Who am I?</button>
      <span class="hint">Enter filters then use the sections below.</span>
    </div>
  </div>

  <!-- Uploads -->
  <div class="panel">
    <h2>Uploads (by Agent/Month)</h2>
    <div class="row">
      <a id="up_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadUploads()">Load</button>
      <span id="up_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>UploadID</th><th>Agent</th><th>Agent Name</th><th>Doc</th><th>File</th>
            <th>Timestamp</th><th>Month</th><th>Active</th>
          </tr>
        </thead>
        <tbody id="up_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Statements -->
  <div class="panel">
    <h2>Statements</h2>
    <div class="row">
      <a id="st_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadStatements()">Load</button>
      <span id="st_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Upload</th><th>Agent</th><th>Policy</th><th>Holder</th>
            <th>Type</th><th>Pay Date</th><th>Receipt</th><th>Premium</th>
            <th>Com %</th><th>Com Amt</th><th>Inception</th><th>Month</th><th>License</th>
          </tr>
        </thead>
        <tbody id="st_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Schedule -->
  <div class="panel">
    <h2>Schedule</h2>
    <div class="row">
      <a id="sc_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadSchedule()">Load</button>
      <span id="sc_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Month</th><th>Schedule ID</th><th>Upload</th><th>Agent</th><th>Name</th>
            <th>Batch</th><th>Total Premiums</th><th>Income</th><th>Total Deductions</th>
            <th>Net Commission</th><th>SICLASE</th><th>Premium Deduction</th><th>Pensions</th><th>Welfareko</th>
          </tr>
        </thead>
        <tbody id="sc_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Terminated -->
  <div class="panel">
    <h2>Terminated</h2>
    <div class="row">
      <label for="te_pol">Policy</label>
      <input id="te_pol" type="text" placeholder="(optional)" />
      <a id="te_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadTerminated()">Load</button>
      <span id="te_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Upload</th><th>Agent</th><th>Policy</th><th>Holder</th><th>Type</th>
            <th>Premium</th><th>Status</th><th>Reason</th><th>Month</th><th>Termination Date</th>
          </tr>
        </thead>
        <tbody id="te_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Active Policies -->
  <div class="panel">
    <h2>Active Policies</h2>
    <div class="row">
      <label for="ap_status">Status</label>
      <select id="ap_status">
        <option value="">(any)</option>
        <option value="ACTIVE">ACTIVE</option>
        <option value="MISSING">MISSING</option>
      </select>
      <a id="ap_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadActive()">Load</button>
      <span id="ap_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Agent</th><th>Policy</th><th>Type</th><th>Holder</th><th>Inception</th>
            <th>First Seen</th><th>Last Seen</th><th>Seen Month</th><th>Last Premium</th>
            <th>Last Com %</th><th>Status</th><th>Consecutive Missing</th>
          </tr>
        </thead>
        <tbody id="ap_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Missing (admin/superuser path lives under /api/agent) -->
  <div class="panel">
    <h2>Missing (Active-as-of minus Statements-In-Month)</h2>
    <div class="row">
      <a id="mi_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadMissing()">Load</button>
      <span id="mi_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Policy</th><th>Holder</th><th>Surname</th><th>Other Name</th><th>Last Seen Month</th><th>Last Premium</th><th>Last Com %</th></tr>
        </thead>
        <tbody id="mi_tbody"></tbody>
      </table>
    </div>
    <p class="small muted">Definition: ACTIVE‑AS‑OF(month) MINUS STATEMENTS‑IN(month). “Active‑as‑of” means seen on/before the month and not terminated on/before the month.</p>
  </div>

  <!-- Commission Comparison -->
  <div class="panel">
    <h2>Commission Comparison</h2>
    <div class="row">
      <a id="cc_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadCommissionComparison()">Load</button>
      <span id="cc_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Expected Net</th><th>Statement Net</th><th>Schedule Net</th>
            <th>Δ vs Expected (Statement)</th><th>Δ vs Expected (Schedule)</th>
            <th>Tax %</th><th>SICLASE</th><th>Welfareko</th>
          </tr>
        </thead>
        <tbody id="cc_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Report Generation -->
  <div class="panel">
    <h2>Generate Monthly Report (Admin)</h2>
    <div class="row">
      <button onclick="generateReport()">Generate</button>
      <span id="gr_info" class="hint"></span>
    </div>
  </div>

  <!-- Audit Flags (if available) -->
  <div class="panel">
    <h2>Audit Flags</h2>
    <div class="row">
      <a id="af_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadAuditFlags()">Load</button>
      <span id="af_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Agent</th><th>Policy</th><th>Month</th>
            <th>Flag</th><th>Severity</th><th>Detail</th>
            <th>Expected</th><th>Actual</th><th>Created</th>
          </tr>
        </thead>
        <tbody id="af_tbody"></tbody>
      </table>
    </div>
  </div>

  <!-- Uploads Tracker -->
  <div class="panel">
    <h2>Uploads Tracker (Last N Months)</h2>
    <div class="row">
      <label>Months back</label>
      <input id="ut_back" type="text" value="36" style="width: 80px;" />
      <a id="ut_csv" class="button-link" href="#">CSV</a>
      <button onclick="loadUploadsTracker()">Load</button>
      <span id="ut_info" class="hint"></span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Month</th><th>Statement?</th><th>Schedule?</th><th>Terminated?</th>
            <th>Statement UploadID</th><th>Schedule UploadID</th><th>Terminated UploadID</th>
          </tr>
        </thead>
        <tbody id="ut_tbody"></tbody>
      </table>
    </div>
  </div>

</main>

<script>
  // DOM helpers
  const $ = (id) => document.getElementById(id);
  const text = (id, v) => { const el = $(id); if (el) el.textContent = v ?? ""; };
  const html = (id, v) => { const el = $(id); if (el) el.innerHTML = v ?? ""; };
  const val = (id) => (($(id) || {}).value || "").trim();
  const clearBody = (id) => { const b = $(id); if (b) b.innerHTML = ""; }
  const appendRow = (id, rowHTML) => { const b = $(id); if (!b) return; const tr = document.createElement('tr'); tr.className='fade'; tr.innerHTML = rowHTML; b.appendChild(tr); };

  // Identity
  async function whoAmI() {
    try {
      const r = await fetch('/api/auth/me', { credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.status !== 'OK') {
        text('who', 'Anonymous');
        return;
      }
      const id = j.identity || {};
      const nm = id.agent_name ?? id.user_email ?? '';
      const code = id.agent_code ?? '';
      const role = id.role ?? '';
      text('who', `${nm}${code ? ' ('+code+')' : ''} — ${role}`);
      text('title', `ICRS — Admin Dashboard`);
      text('subtitle', `Signed in as: ${nm}${code ? ' ('+code+')' : ''} — ${role}`);
    } catch (e) {
      text('who', 'Error determining identity');
    }
  }

  // CSRF helper for POSTs
  async function getCsrf() {
    const r = await fetch('/api/auth/csrf', { credentials:'same-origin' });
    if (!r.ok) throw new Error('Failed CSRF');
    const j = await r.json();
    return j.csrf_token;
  }

  // Uploads
  async function loadUploads() {
    const agent = val('f_agent'); const month = val('f_month');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month);
    const csv = '/api/admin/uploads.csv?' + q.toString();
    $('up_csv').href = csv;
    text('up_info','Loading…'); clearBody('up_tbody');
    const r = await fetch('/api/admin/uploads?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(u => {
      appendRow('up_tbody',
        `<td>${u.UploadID ?? ''}</td><td>${u.agent_code ?? ''}</td><td>${u.AgentName ?? ''}</td>
         <td>${u.doc_type ?? ''}</td><td>${u.FileName ?? ''}</td><td>${u.UploadTimestamp ?? ''}</td>
         <td>${u.month_year ?? ''}</td><td>${u.is_active ?? 0}</td>`);
    });
    text('up_info', `Items: ${j.count ?? 0}`);
  }

  // Statements
  async function loadStatements() {
    const agent = val('f_agent'); const month = val('f_month');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month);
    $('st_csv').href = '/api/admin/statements.csv?' + q.toString();
    text('st_info','Loading…'); clearBody('st_tbody');
    const r = await fetch('/api/admin/statements?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(s => {
      appendRow('st_tbody',
        `<td>${s.statement_id ?? ''}</td><td>${s.upload_id ?? ''}</td><td>${s.agent_code ?? ''}</td>
         <td>${s.policy_no ?? ''}</td><td>${s.holder ?? ''}</td><td>${s.policy_type ?? ''}</td>
         <td>${s.pay_date ?? ''}</td><td>${s.receipt_no ?? ''}</td><td>${s.premium ?? ''}</td>
         <td>${s.com_rate ?? ''}</td><td>${s.com_amt ?? ''}</td><td>${s.inception ?? ''}</td>
         <td>${s.month_year ?? ''}</td><td>${s.AGENT_LICENSE_NUMBER ?? ''}</td>`);
    });
    text('st_info', `Items: ${j.count ?? 0}`);
  }

  // Schedule
  async function loadSchedule() {
    const agent = val('f_agent'); const month = val('f_month');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month);
    $('sc_csv').href = '/api/admin/schedule.csv?' + q.toString();
    text('sc_info','Loading…'); clearBody('sc_tbody');
    const r = await fetch('/api/admin/schedule?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(sc => {
      appendRow('sc_tbody',
        `<td>${sc.month_year ?? ''}</td><td>${sc.schedule_id ?? ''}</td><td>${sc.upload_id ?? ''}</td>
         <td>${sc.agent_code ?? ''}</td><td>${sc.agent_name ?? ''}</td><td>${sc.commission_batch_code ?? ''}</td>
         <td>${sc.total_premiums ?? ''}</td><td>${sc.income ?? ''}</td><td>${sc.total_deductions ?? ''}</td>
         <td>${sc.net_commission ?? ''}</td><td>${sc.siclase ?? ''}</td><td>${sc.premium_deduction ?? ''}</td>
         <td>${sc.pensions ?? ''}</td><td>${sc.welfareko ?? ''}</td>`);
    });
    text('sc_info', `Items: ${j.count ?? 0}`);
  }

  // Terminated
  async function loadTerminated() {
    const agent = val('f_agent'); const month = val('f_month'); const pol = val('te_pol');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month); if (pol) q.append('policy_no', pol);
    $('te_csv').href = '/api/admin/terminated.csv?' + q.toString();
    text('te_info','Loading…'); clearBody('te_tbody');
    const r = await fetch('/api/admin/terminated?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(t => {
      appendRow('te_tbody',
        `<td>${t.terminated_id ?? ''}</td><td>${t.upload_id ?? ''}</td><td>${t.agent_code ?? ''}</td>
         <td>${t.policy_no ?? ''}</td><td>${t.holder ?? ''}</td><td>${t.policy_type ?? ''}</td>
         <td>${t.premium ?? ''}</td><td>${t.status ?? ''}</td><td>${t.reason ?? ''}</td>
         <td>${t.month_year ?? ''}</td><td>${t.termination_date ?? ''}</td>`);
    });
    text('te_info', `Items: ${j.count ?? 0}`);
  }

  // Active policies
  async function loadActive() {
    const agent = val('f_agent'); const month = val('f_month'); const status = val('ap_status');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month); if (status) q.append('status', status);
    $('ap_csv').href = '/api/admin/active-policies.csv?' + q.toString();
    text('ap_info','Loading…'); clearBody('ap_tbody');
    const r = await fetch('/api/admin/active-policies?' + q.toString(), { credentials:'same-origin' });
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
  }

  // Missing (admin/superuser path exported from /api/agent)
  async function loadMissing() {
    const agent = val('f_agent'); const month = val('f_month');
    if (!agent || !month) { alert('Provide agent & month'); return; }
    const q = new URLSearchParams({ agent_code: agent, month_year: month });
    $('mi_csv').href = '/api/agent/missing/by-agent.csv?' + q.toString();
    text('mi_info','Loading…'); clearBody('mi_tbody');
    const r = await fetch('/api/agent/missing/by-agent?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(m => {
      appendRow('mi_tbody',
        `<td>${m.policy_no ?? ''}</td><td>${m.holder_name ?? ''}</td><td>${m.holder_surname ?? ''}</td>
         <td>${m.other_name ?? ''}</td><td>${m.last_seen_month ?? ''}</td><td>${m.last_premium ?? ''}</td>
         <td>${m.last_com_rate ?? ''}</td>`);
    });
    text('mi_info', `Items: ${j.count ?? 0}`);
  }

  // Commission comparison
  async function loadCommissionComparison() {
    const agent = val('f_agent'); const month = val('f_month');
    if (!agent || !month) { alert('Provide agent & month'); return; }
    const q = new URLSearchParams({ agent_code: agent, month_year: month, include_raw: '1' });
    $('cc_csv').href = '/api/admin/reports/commission-comparison.csv?' + new URLSearchParams({ agent_code: agent, month_year: month }).toString();
    text('cc_info','Loading…'); clearBody('cc_tbody');
    const r = await fetch('/api/admin/reports/commission-comparison?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    const net = j.net ?? {}; const dif = j.diffs_vs_expected ?? {}; const inp = j.inputs ?? {};
    appendRow('cc_tbody',
      `<td>${net.expected ?? 0}</td><td>${net.statement ?? 0}</td><td>${net.schedule ?? 0}</td>
       <td>${(dif.statement?.amount ?? 0)} (${(dif.statement?.percent ?? 0)}%)</td>
       <td>${(dif.schedule?.amount ?? 0)} (${(dif.schedule?.percent ?? 0)}%)</td>
       <td>${inp.tax_percent ?? 0}</td><td>${inp.siclase ?? 0}</td><td>${inp.welfareko ?? 0}</td>`);
    text('cc_info','Done');
  }

  // Report generation (admin)
  async function generateReport() {
    const agent = val('f_agent'); const month = val('f_month');
    if (!agent || !month) { text('gr_info','Agent & Month required'); return; }
    text('gr_info','Generating…');
    try {
      const csrf = await getCsrf();
      const r = await fetch('/api/admin/reports/generate-agent-month', {
        method:'POST',
        headers:{ 'Content-Type':'application/x-www-form-urlencoded', 'X-CSRF-Token': csrf },
        body: new URLSearchParams({ agent_code: agent, month_year: month }),
        credentials:'same-origin'
      });
      const j = await r.json().catch(()=>({}));
      if (!r.ok) { text('gr_info', j.detail ?? 'Failed'); return; }
      text('gr_info', j.message ?? 'Generated');
    } catch (err) {
      text('gr_info', String(err) || 'Error');
    }
  }

  // Audit flags (if the endpoint is present)
  async function loadAuditFlags() {
    const agent = val('f_agent'); const month = val('f_month');
    const q = new URLSearchParams(); if (agent) q.append('agent_code', agent); if (month) q.append('month_year', month);
    $('aftd>${a.id ?? ''}</td><td>${a.agent_code ?? ''}</td><td>${a.policy_no ?? ''}</td><td>${a.month_year ?? ''}</td>
         <td>${a.flag_type ?? ''}</td><td>${a.severity ?? ''}</td><td>${a.flag_detail ?? ''}</td>
         <td>${a.expected_value ?? ''}</td><td>${a.actual_value ?? ''}</td><td>${a.created_at ?? ''}</td>`);
    });
    text('af_info', `Items: ${j.count ?? 0}`);
  }

  // Uploads tracker (admin view)
  async function loadUploadsTracker() {
    const agent = val('f_agent'); const back = (val('ut_back') || '36');
    if (!agent) { alert('Provide agent'); return; }
    const q = new URLSearchParams({ agent_code: agent, months_back: back });
    $('ut_csv').href = '/api/admin/uploads/tracker.csv?' + q.toString();
    text('ut_info','Loading…'); clearBody('ut_tbody');
    const r = await fetch('/api/admin/uploads/tracker?' + q.toString(), { credentials:'same-origin' });
    const j = await r.json();
    (j.items ?? []).forEach(u => {
      const yesNo = (v) => (v ? '<span class="ok">YES</span>' : '<span class="bad">NO</span>');
      appendRow('ut_tbody',
        `<td>${u.month_year ?? ''}</td><td>${yesNo(u.statement_present)}</td><td>${yesNo(u.schedule_present)}</td>
         <td>${yesNo(u.terminated_present)}</td><td>${u.statement_upload_id ?? ''}</td>
         <td>${u.schedule_upload_id ?? ''}</td><td>${u.terminated_upload_id ?? ''}</td>`);
    });
    text('ut_info', `Items: ${j.count ?? 0}`);
  }

  // Initial identity
  whoAmI();
</script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard() -> HTMLResponse:
    return HTMLResponse(_PAGE)
