
# src/ui/admin_dashboard.py
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui/admin", tags=["UI Admin"])

_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ICRS · Admin Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet"/>
  <style>
    :root {
      --bg: #0b1020;
      --panel: #0f172a;
      --panel-2: #111827;
      --line: #1f2937;
      --text: #e5e7eb;
      --text-soft: #9ca3af;
      --accent: #2563eb;
      --accent-alt: #22d3ee;
      --accent-soft: rgba(37,99,235,.12);
      --warn: #fbbf24;
    }
    html, body { background: var(--bg); color: var(--text); font-family: system-ui,-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif; height:100%; }
    .navbar { background: #0f172a; border-bottom:1px solid var(--line); }
    .badge-soft { background: rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.2); border-radius:999px; padding:.2rem .6rem; }
    .shell { display:grid; grid-template-columns: 260px 1fr; gap:1rem; min-height: calc(100vh - 52px); }
    .left-nav { background: var(--panel); border-right:1px solid var(--line); padding:1rem; }
    .brand-title { display:flex; align-items:center; gap:.5rem; font-weight:800; }
    .idcard { border-radius:12px; background:#0b1327; }
    .nav .nav-link { color: var(--text); border-radius: 10px; }
    .nav .nav-link.active { background: #172138; }
    .main { padding: 1rem; }
    .cardy { background: var(--panel); border:1px solid var(--line); border-radius:12px; }
    .table { color: var(--text); }
    .table thead th { color:#93c5fd; border-color:#233148; font-size:.85rem; }
    .table td, .table th { border-color: var(--line); }
    .text-dim { color: var(--text-soft) !important; }
    .btn-primary { background: #2563eb; border-color:#2563eb; }
    .btn-outline-secondary { color: var(--text); border-color:#4b5563; }
    .section { display:none; }
    .section.active { display:block; }
    .kpi { font-weight:800; font-size:1.1rem; }
    .grid { display:grid; gap:1rem; grid-template-columns: repeat(12, 1fr); }
    .col-12 { grid-column: span 12; }
    .col-6 { grid-column: span 6; }
    .col-4 { grid-column: span 4; }
    .col-3 { grid-column: span 3; }
    .mt-2 { margin-top:.5rem; } .mt-3 { margin-top:1rem; } .mt-4 { margin-top:1.5rem; }
    .mb-2 { margin-bottom:.5rem; } .mb-3 { margin-bottom:1rem; } .mb-4 { margin-bottom:1.5rem; }
    .small-muted { font-size:.85rem; color: var(--text-soft); }
  </style>
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark">
    <div class="container-fluid" style="max-width:1300px;">
      <a class="navbar-brand" href="/ui/"><i class="bi bi-shield-shaded me-2"></i>ICRS Admin</a>
      <div class="d-flex gap-2">
        <a class="btn btn-sm btn-outline-light" href="/ui/">Home</a>
        <a class="btn btn-sm btn-outline-warning" href="/api/auth/logout">Logout</a>
      </div>
    </div>
  </nav>

  <div class="shell">
    <!-- LEFT NAV -->
    <div class="left-nav">
      <div class="brand-title mb-3">
        <span style="font-size:20px">🛡️</span>
        <div>Admin</div>
      </div>

      <div class="idcard p-3 mb-3 border border-1 border-secondary-subtle">
        <div class="d-flex align-items-center justify-content-between">
          <div class="text-dim">Identity</div>
          <span id="rolePill" class="badge-soft">…</span>
        </div>
        <div class="small-muted mt-2">Only <b>admin</b> (or superuser) can access this view.</div>
        <div class="d-grid mt-2">
          <button class="btn btn-sm btn-outline-secondary" onclick="bootstrapAdmin()">Re-check</button>
        </div>
      </div>

      <ul class="nav nav-pills flex-column">
        <li class="nav-item"><a href="#" class="nav-link active" data-target="sec-uploads" onclick="navTo(event)">Recent uploads</a></li>
        <li class="nav-item"><a href="#" class="nav-link" data-target="sec-missing" onclick="navTo(event)">Missing by Agent</a></li>
        <li class="nav-item"><a href="#" class="nav-link" data-target="sec-gen" onclick="navTo(event)">Generate Agent Month</a></li>
      </ul>
    </div>

    <!-- MAIN -->
    <div class="main">
      <!-- Recent uploads -->
      <section id="sec-uploads" class="section active">
        <div class="cardy p-3">
          <div class="d-flex align-items-center justify-content-between">
            <div class="fw-bold"><i class="bi bi-cloud-arrow-up me-2"></i>Recent uploads</div>
          </div>

          <div class="row g-2 mt-1">
            <div class="col-4">
              <label class="small-muted">Agent code</label>
              <input id="uAgent" class="form-control form-control-sm" placeholder="Optional"/>
            </div>
            <div class="col-4">
              <label class="small-muted">Month label</label>
              <input id="uMonth" class="form-control form-control-sm" placeholder="Jun 2025 (optional)"/>
            </div>
            <div class="col-4 d-grid align-items-end">
              <button class="btn btn-sm btn-outline-light" onclick="loadUploads()">Load</button>
            </div>
          </div>

          <div class="table-responsive mt-2">
            <table class="table table-sm table-borderless align-middle">
              <thead><tr>
                <th>ID</th><th>Type</th><th>Agent</th><th>Month</th><th>File</th><th>Active</th>
              </tr></thead>
              <tbody id="upTbody"><tr><td colspan="6" class="small-muted">None loaded.</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- Missing by agent -->
      <section id="sec-missing" class="section">
        <div class="cardy p-3">
          <div class="fw-bold"><i class="bi bi-search me-2"></i>Missing by Agent (helper path avoids collision)</div>

          <div class="row g-2 mt-2">
            <div class="col-6">
              <label class="small-muted">Agent code</label>
              <input id="missAgent" class="form-control form-control-sm" placeholder="Agent code"/>
            </div>
            <div class="col-6">
              <label class="small-muted">Month label</label>
              <input id="missMonth" class="form-control form-control-sm" placeholder="Jun 2025"/>
            </div>
          </div>

          <div class="d-grid gap-2 mt-2">
            <button class="btn btn-sm btn-outline-info" onclick="loadMissing()">Load</button>
            <a id="missCsv" class="btn btn-sm btn-outline-light disabled" role="button">Download CSV</a>
          </div>

          <div class="mt-3">
            <div class="small-muted mb-1">Results</div>
            <pre id="out" class="small-muted m-0" style="white-space:pre-wrap"></pre>
          </div>
        </div>
      </section>

      <!-- Generate -->
      <section id="sec-gen" class="section">
        <div class="cardy p-3">
          <div class="fw-bold"><i class="bi bi-hammer me-2"></i>Generate Agent Month</div>

          <div class="row g-2 mt-2">
            <div class="col-6">
              <label class="small-muted">Agent code</label>
              <input id="genAgent" class="form-control form-control-sm" placeholder="Agent code"/>
            </div>
            <div class="col-6">
              <label class="small-muted">Month label</label>
              <input id="genMonth" class="form-control form-control-sm" placeholder="Jun 2025"/>
            </div>
          </div>

          <div class="d-grid gap-2 mt-2">
            <button class="btn btn-sm btn-primary" onclick="generateAgentMonth()">Generate</button>
          </div>

          <div id="genMsg" class="small-muted mt-2">—</div>
        </div>
      </section>
    </div>
  </div>

  <div class="text-center small-muted mt-4 pb-3">
    Admin tools rely on: <code>/api/auth/me</code>, <code>/api/admin/uploads</code>,
    <code>/api/admin/reports/generate-agent-month</code>, and
    <code>/api/agent/missing/by-agent</code>.
  </div>

<script>
function navTo(e){
  e.preventDefault();
  const t = e.currentTarget.getAttribute('data-target');
  document.querySelectorAll('.nav .nav-link').forEach(a => a.classList.remove('active'));
  e.currentTarget.classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(t).classList.add('active');
}

function qs(sel){return document.querySelector(sel);}
function fmt(n){return Number(n||0).toLocaleString(undefined,{maximumFractionDigits:2});}
async function j(url,opt){const r=await fetch(url,Object.assign({credentials:"same-origin"},opt||{})); if(!r.ok)throw new Error((await r.text())||r.statusText); const ct=r.headers.get("content-type")||""; return ct.includes("application/json")?r.json():r.text();}

async function bootstrapAdmin(){
  const me = await j("/api/auth/me");
  const id = (me && me.identity) || {};
  const role = (id.role||"").toLowerCase();
  qs("#rolePill").textContent = role || "anon";
  if (role !== "admin" && role !== "superuser") {
    window.location.href = "/ui/login/admin"; return;
  }
}

async function loadUploads(){
  const agent = (qs("#uAgent").value||"").trim();
  const month = (qs("#uMonth").value||"").trim();
  const p = new URLSearchParams();
  if(agent) p.set("agent_code", agent);
  if(month) p.set("month_year", month);
  // /api/admin/uploads → {count, items:[{UploadID, agent_code, doc_type, FileName, is_active, month_year, ...}]}
  const data = await j("/api/admin/uploads?"+p.toString());
  const items = data.items||[];
  qs("#upTbody").innerHTML = items.length ? items.map(row => {
    return `<tr>
      <td>${row.UploadID}</td>
      <td>${row.doc_type}</td>
      <td>${row.agent_code} · <span class="text-dim">${row.AgentName||""}</span></td>
      <td><code>${row.month_year||""}</code></td>
      <td class="small-muted">${row.FileName||""}</td>
      <td>${Number(row.is_active)===1?"✓":"—"}</td>
    </tr>`;
  }).join("") : `<tr><td colspan="6" class="small-muted">No uploads</td></tr>`;
}

async function loadMissing(){
  const ac = (qs("#missAgent").value||"").trim();
  const m = (qs("#missMonth").value||"").trim();
  if(!ac || !m){ qs("#out").textContent="Provide agent code and month"; return; }
  // helper endpoint lives under /api/agent/missing/by-agent to avoid collision
  const url = `/api/agent/missing/by-agent?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(m)}`;
  const res = await j(url);
  const rows = (res.items||[]).map(r => `${r.policy_no||""}\t${r.holder_name||""}\t${r.last_seen_month||""}\t${fmt(r.last_premium)}\t${r.last_com_rate??""}`).join("\n");
  qs("#out").textContent = rows || "(no rows)";
  const csv = `/api/agent/missing/by-agent.csv?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(m)}`;
  const a = qs("#missCsv");
  a.classList.remove("disabled");
  a.href = csv;
}

async function getCsrf(){
  const s = await j("/api/auth/csrf");
  return s.csrf_token;
}

async function generateAgentMonth(){
  const ac = (qs("#genAgent").value||"").trim();
  const m = (qs("#genMonth").value||"").trim();
  if(!ac || !m){ qs("#genMsg").textContent = "Agent code and month are required."; return; }
  const csrf = await getCsrf();
  const body = new URLSearchParams({agent_code: ac, month_year: m});
  // /api/admin/reports/generate-agent-month → {status, message, ...}
  try{
    const r = await fetch("/api/admin/reports/generate-agent-month", {
      method:"POST",
      headers: {"Content-Type":"application/x-www-form-urlencoded", "X-CSRF-Token": csrf},
      body, credentials:"same-origin"
    });
    const txt = await r.text();
    qs("#genMsg").textContent = r.ok ? "Triggered ✓" : ("Failed: "+txt);
  }catch(err){
    qs("#genMsg").textContent = "Failed: "+String(err||"");
  }
}

(async () => {
  await bootstrapAdmin();      // /api/auth/me
  await loadUploads();         // /api/admin/uploads
})();
</script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard_index() -> HTMLResponse:
    return HTMLResponse(_PAGE)