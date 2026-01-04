
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from src.api.ui_pages import _get_current_user

router = APIRouter(tags=["Superuser Dashboard"])

@router.get("/ui/superuser", response_class=HTMLResponse)
async def superuser_dashboard(request: Request):
    # ---- Cookie-based guard ----
    u = _get_current_user(request) or {}
    role = str(u.get("role") or "").lower()
    if role != "superuser":
        return RedirectResponse(url="/ui/login?role=superuser", status_code=302)

    # ---- Full UI ----
    html = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Superuser Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
  <style>
    :root{
      --bg:#0a0f1f; --panel:#0d1428; --accent:#06d6a0; --accent-2:#8a5cf6;
      --warn:#f59e0b; --ok:#10b981; --danger:#ef4444; --muted:#9ca3af; --text:#e5e7eb; --white:#ffffff;
    }
    body { background:linear-gradient(135deg, #0a0f1f 0%, #0d1428 100%); color:var(--text); }
    a, a:hover { color: var(--accent); text-decoration: none; }
    .sidebar { width:300px; position:fixed; top:0; left:0; bottom:0; background:linear-gradient(180deg,#0d1428,#0a0f1f); color:#fff; padding:22px; overflow-y:auto; }
    .nav-link { color:rgba(255,255,255,.92); cursor:pointer; padding:8px 12px; display:block; }
    .nav-link.active, .nav-link:hover { background:rgba(138,92,246,.20); border-left:3px solid var(--accent-2); border-radius:.35rem; }
    main { margin-left:300px; padding:28px; }
    .panel { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:18px; backdrop-filter: blur(3px); }
    .toolbar { display:flex; gap:8px; align-items:center; justify-content:space-between; }
    .badge-ok { background: var(--ok); }
    .badge-no { background: var(--danger); }
    .text-kicker { text-transform:uppercase; font-size:.76rem; color:var(--muted); letter-spacing:.08em; }
    .btn-accent { background: var(--accent-2); color: var(--white); }
    .btn-outline-accent { border-color: var(--accent-2); color: var(--accent-2); }
    .btn-outline-accent:hover { background: var(--accent-2); color: var(--white); }
    select.form-select, input.form-control { background:#0f1b33; color:#dbeafe; border:1px solid #1f2937; }
    .section { display:none; }
    .section.active { display:block; }
    .id-box { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); padding:10px; border-radius:10px; margin-bottom:10px; }
    .code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div class="d-flex align-items-center mb-3">
      <i class="bi bi-shield-lock-fill me-2" style="color:var(--accent-2)"></i>
      <h5 class="mb-0">Superuser Dashboard</h5>
    </div>

    <div class="mb-3">
      <a class="nav-link" href="/ui/"><i class="bi bi-house me-2"></i>Landing</a>
      <a class="nav-link" href="/ui/agent"><i class="bi bi-person-circle me-2"></i>Agent Dashboard</a>
      <a class="nav-link" href="/ui/admin"><i class="bi bi-gear me-2"></i>Admin Dashboard</a>
      <a class="nav-link" onclick="logout()"><i class="bi bi-box-arrow-right me-2"></i>Logout</a>
    </div>

    <div class="text-kicker mt-3 mb-1">Uploads &amp; Tools</div>
    <a class="nav-link active" onclick="showSection('uploads',event); loadUploads();"><i class="bi bi-cloud-arrow-up me-2"></i>Uploads</a>
    <a class="nav-link" onclick="showSection('deactivate',event)"><i class="bi bi-shield-check me-2"></i>Deactivate Older</a>
    <a class="nav-link" onclick="showSection('tracker',event);"><i class="bi bi-check2-circle me-2"></i>Upload Tracker</a>

    <div class="text-kicker mt-3 mb-1">Data Explorer</div>
    <a class="nav-link" onclick="showSection('statements',event); loadStatements();"><i class="bi bi-file-text me-2"></i>Statements</a>
    <a class="nav-link" onclick="showSection('schedules',event); loadSchedules();"><i class="bi bi-calendar3 me-2"></i>Schedules</a>
    <a class="nav-link" onclick="showSection('terminated',event); loadTerminated();"><i class="bi bi-x-circle me-2"></i>Terminated</a>
    <a class="nav-link" onclick="showSection('activepol',event); loadActivePolicies();"><i class="bi bi-shield-shaded me-2"></i>Active Policies</a>
    <a class="nav-link" onclick="showSection('missingpol',event); loadMissing();"><i class="bi bi-search me-2"></i>Missing Policies</a>

    <div class="text-kicker mt-3 mb-1">Audit &amp; Reports</div>
    <a class="nav-link" onclick="showSection('audit',event); loadAuditFlags();"><i class="bi bi-flag me-2"></i>Audit Flags</a>
    <a class="nav-link" onclick="showSection('monthly',event);"><i class="bi bi-diagram-3 me-2"></i>Monthly Reports</a>

    <div class="mt-3">
      <a class="nav-link" href="/docs" target="_blank"><i class="bi bi-journal-code me-2"></i>API Docs</a>
    </div>
  </aside>

  <main>
    <div class="id-box">
      <div class="small text-muted">Identity headers for wrapper APIs (stored in localStorage).</div>
      <div class="row g-2">
        <div class="col-md-4"><input id="id_user_id" class="form-control" placeholder="x-user-id (integer)"></div>
        <div class="col-md-4"><input id="id_role" class="form-control" placeholder="x-user-role (superuser)" value="superuser"></div>
        <div class="col-md-4"><input id="id_agent" class="form-control" placeholder="x-user-agent (optional)"></div>
        <div class="col-md-12 d-flex justify-content-end"><button class="btn btn-outline-accent btn-sm" onclick="saveIdentity()">Save identity</button></div>
      </div>
    </div>

    <!-- Uploads -->
    <section id="uploads" class="panel section active">
      <div class="toolbar">
        <h4 class="mb-0">Uploads</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadUploadsCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="up_agent" class="form-control" placeholder="e.g. 9518"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="up_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Doc Type</label>
          <select id="up_doc" class="form-select"><option value="">- doc type -</option><option value="STATEMENT">STATEMENT</option><option value="SCHEDULE">SCHEDULE</option><option value="TERMINATED">TERMINATED</option></select>
        </div>
        <div class="col-md-3 d-flex align-items-end">
          <button class="btn btn-accent w-100" onclick="loadUploads()">Load</button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-dark table-hover" id="uploads_table">
          <thead><tr><th>ID</th><th>Agent</th><th>DocType</th><th>File</th><th>Month</th><th>Timestamp</th><th>Active</th><th>Actions</th></tr></thead>
          <tbody id="up_tbody"><tr><td colspan="8" class="text-muted text-center">Enter filters and click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Deactivate Older -->
    <section id="deactivate" class="panel section">
      <h4 class="mb-3">Deactivate Older Uploads</h4>
      <form class="row g-3" onsubmit="event.preventDefault(); deactivateOlder();">
        <div class="col-md-3"><label class="form-label">Agent *</label><input id="dec_agent" class="form-control" required></div>
        <div class="col-md-3"><label class="form-label">Month *</label><select id="dec_month" class="form-select" required></select></div>
        <div class="col-md-3"><label class="form-label">Doc Type *</label>
          <select id="dec_doc" class="form-select" required><option value="STATEMENT">STATEMENT</option><option value="SCHEDULE">SCHEDULE</option><option value="TERMINATED">TERMINATED</option></select>
        </div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-warning w-100">Deactivate Older</button></div>
      </form>
      <div id="dec_result" class="mt-2 small"></div>
    </section>

    <!-- Upload Tracker -->
    <section id="tracker" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Upload Tracker</h4>
        <div class="small text-muted">Shows last 36 months per agent (active uploads only).</div>
      </div>
      <div class="row g-3 mt-1">
        <div class="col-md-3"><label class="form-label">Agent</label><input id="trk_agent" class="form-control"></div>
        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadTracker()">Show</button></div>
        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-outline-accent w-100" onclick="downloadTrackerCSV()">CSV</button></div>
      </div>
      <div class="table-responsive mt-3">
        <table class="table table-sm table-dark table-hover">
          <thead><tr><th>Month</th><th>Statement</th><th>Schedule</th></tr></thead>
          <tbody id="trk_tbody"><tr><td colspan="3" class="text-muted text-center">Choose agent</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Statements -->
    <section id="statements" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Statements</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadStatementsCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="stmt_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="stmt_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Policy No</label><input id="stmt_policy" class="form-control"></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadStatements()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="statements_table">
          <thead><tr>
            <th>ID</th><th>Agent</th><th>Policy</th><th>Holder</th><th>Type</th><th>Pay Date</th>
            <th>Premium</th><th>Commission</th><th>Month</th>
          </tr></thead>
          <tbody id="stmt_tbody"><tr><td colspan="9" class="text-muted text-center">Click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Schedules -->
    <section id="schedules" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Schedules</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadSchedulesCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="sch_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="sch_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Latest Only</label><select id="sch_latest" class="form-select"><option value="1" selected>Yes</option><option value="0">No</option></select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadSchedules()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="schedules_table">
          <thead><tr>
            <th>ID</th><th>Agent</th><th>Batch</th><th>Total Premium</th><th>Income</th><th>Deductions</th><th>Net Commission</th><th>Month</th>
          </tr></thead>
          <tbody id="sch_tbody"><tr><td colspan="8" class="text-muted text-center">Click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Terminated -->
    <section id="terminated" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Terminated</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadTerminatedCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="ter_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="ter_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Policy No</label><input id="ter_policy" class="form-control"></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadTerminated()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="terminated_table">
          <thead><tr><th>ID</th><th>Agent</th><th>Policy</th><th>Holder</th><th>Status</th><th>Reason</th><th>Month</th><th>Termination Date</th></tr></thead>
          <tbody id="ter_tbody"><tr><td colspan="8" class="text-muted text-center">Click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Active Policies -->
    <section id="activepol" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Active Policies</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadActivePoliciesCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="ap_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Last Seen Month</label><select id="ap_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Status</label>
          <select id="ap_status" class="form-select"><option value="">- status -</option><option value="ACTIVE">ACTIVE</option><option value="MISSING">MISSING</option><option value="LAPSED">LAPSED</option><option value="TERMINATED">TERMINATED</option></select>
        </div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadActivePolicies()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="active_table">
          <thead><tr><th>ID</th><th>Agent</th><th>Policy</th><th>Type</th><th>Holder</th><th>Last Seen</th><th>Premium</th><th>Status</th></tr></thead>
          <tbody id="active_tbody"><tr><td colspan="8" class="text-muted text-center">Click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Missing Policies -->
    <section id="missingpol" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Missing Policies</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadMissingCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent</label><input id="mp_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="mp_month" class="form-select"></select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadMissing()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="missing_table">
          <thead><tr><th>Policy</th><th>Last Seen Month</th><th>Last Premium</th></tr></thead>
          <tbody id="missing_tbody"><tr><td colspan="3" class="text-muted text-center">Select agent &amp; month</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Audit Flags -->
    <section id="audit" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Audit Flags</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadAuditFlagsCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent</label><input id="af_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month</label><select id="af_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Resolved?</label><select id="af_resolved" class="form-select"><option value="">-</option><option value="1">true</option><option value="0">false</option></select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadAuditFlags()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="audit_table">
          <thead><tr><th>ID</th><th>Agent</th><th>Policy</th><th>Month</th><th>Type</th><th>Severity</th><th>Detail</th><th>Resolved</th></tr></thead>
          <tbody id="audit_tbody"><tr><td colspan="8" class="text-muted text-center">Click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Monthly Reports -->
    <section id="monthly" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Monthly Reports</h4>
        <div class="small text-muted">Generate single-agent report by month (PDF generated; expected commissions inserted).</div>
      </div>
      <form class="row g-3 mt-2" onsubmit="event.preventDefault(); generateMonthlyAgentMonth();">
        <div class="col-md-3"><label class="form-label">Agent (optional)</label><input id="mr_agent" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">Month *</label><select id="mr_month" class="form-select" required></select></div>
        <div class="col-md-3"><label class="form-label">Agent Name (optional)</label><input id="mr_agent_name" class="form-control" placeholder="Auto/fallback to agent code"></div>
        <div class="col-md-3"><label class="form-label">Upload ID (optional)</label><input id="mr_upload_id" class="form-control" type="number" min="1" placeholder="Use latest active if omitted"></div>
        <div class="col-md-3"><label class="form-label">Output Folder</label><input id="mr_out" class="form-control code" value="D:/PROJECT/INSURANCELOCAL/reports"></div>
        <div class="col-md-2"><label class="form-label">User ID</label><input id="mr_user_id" class="form-control" type="number" placeholder="Optional"></div>
        <div class="col-md-4 d-flex align-items-end"><button class="btn btn-accent w-100"><i class="bi bi-play-fill"></i> Generate</button></div>
      </form>
      <div id="mr_result" class="mt-3"></div>
    </section>
  </main>

  <script>
    function saveIdentity(){
      localStorage.setItem('id_user_id', document.getElementById('id_user_id').value.trim());
      localStorage.setItem('id_role',  document.getElementById('id_role').value.trim());
      localStorage.setItem('id_agent', document.getElementById('id_agent').value.trim());
      alert('Identity saved. Requests will include x-user-* headers.');
    }
    function headers(){
      return {
        'x-user-id':   localStorage.getItem('id_user_id') || '',
        'x-user-role': localStorage.getItem('id_role')     || 'superuser',
        'x-user-agent':localStorage.getItem('id_agent')    || ''
      };
    }
    function logout(){ try{ localStorage.clear(); sessionStorage.clear(); }catch(e){} window.location.href = "/ui/"; }

    function showSection(id, ev){
      document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));
      let target = null;
      if (ev) { try { if (ev.target) target = ev.target.closest ? ev.target.closest('.nav-link') : null; else if (ev.classList && ev.classList.contains && ev.classList.contains('nav-link')) target = ev; } catch (e) { target = null; } }
      if (target && target.classList) target.classList.add('active');
      document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
      const sec = document.getElementById(id); if (sec) sec.classList.add('active');
    }

    function generateMonths(n=36){
      const out=[], abbr=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const now=new Date(); let y=now.getFullYear(), m=now.getMonth();
      for(let i=0;i<n;i++){ const mm=(m-i); const year=y+Math.floor(mm/12); const mon=((mm%12)+12)%12; out.push(`${abbr[mon]} ${year}`); }
      return out;
    }
    function populateMonthSelects(){
      const labels=generateMonths(36);
      ['up_month','dec_month','stmt_month','sch_month','ter_month','ap_month','mp_month','af_month','mr_month']
        .forEach(id=>{ const el=document.getElementById(id); if(!el) return; el.innerHTML=''; labels.forEach(l=>{ const opt=document.createElement('option'); opt.value=l; opt.textContent=l; el.appendChild(opt); }); });
    }

    async function loadUploads(){
      const params=new URLSearchParams();
      const ac=document.getElementById('up_agent').value.trim();
      const mm=document.getElementById('up_month').value;
      const dt=document.getElementById('up_doc').value;
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt);
      const r=await fetch(`/api/superuser/uploads?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('up_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No uploads</td></tr>';
      rows.forEach(u=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${u.UploadID}</td><td>${u.agent_code||''}</td><td>${u.doc_type||''}</td><td>${u.FileName||''}</td>
          <td>${u.month_year||''}</td><td>${u.UploadTimestamp||''}</td><td>${u.is_active?'1':'0'}</td>
          <td>${u.is_active? `<button class="btn btn-sm btn-outline-danger" onclick="deactivateUpload(${u.UploadID})">Deactivate</button>`
                           : `<button class="btn btn-sm btn-outline-success" onclick="enableUpload(${u.UploadID})">Enable</button>`}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadUploadsCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('up_agent').value.trim();
      const mm=document.getElementById('up_month').value;
      const dt=document.getElementById('up_doc').value;
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt);
      window.open(`/api/admin/uploads.csv?${params.toString()}`,'_blank');
    }
    async function deactivateUpload(id){ await fetch(`/api/admin/uploads/${id}`,{method:'DELETE'}); await loadUploads(); }
    async function enableUpload(id){ await fetch(`/api/admin/uploads/enable/${id}`,{method:'POST'}); await loadUploads(); }

    async function deactivateOlder(){
      const body={ agent_code: document.getElementById('dec_agent').value.trim(),
                   month_year: document.getElementById('dec_month').value,
                   doc_type: document.getElementById('dec_doc').value };
      const r=await fetch('/api/admin/uploads/deactivate-older',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const j=await r.json(); document.getElementById('dec_result').innerText=JSON.stringify(j); await loadUploads();
    }

    async function loadTracker(){
      const ac=document.getElementById('trk_agent').value.trim();
      if(!ac){ document.getElementById('trk_tbody').innerHTML='<tr><td colspan="3" class="text-muted text-center">Choose agent</td></tr>'; return; }
      const r=await fetch(`/api/superuser/uploads/tracker?agent_code=${encodeURIComponent(ac)}&months_back=36`, {headers: headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('trk_tbody'); tb.innerHTML='';
      if(!rows.length){ tb.innerHTML='<tr><td colspan="3" class="text-muted text-center">No data</td></tr>'; return; }
      rows.forEach(x=>{
        const s=x.statement? `<span class="badge badge-ok">✓</span>`:`<span class="badge badge-no">✗</span>`;
        const sc=x.schedule? `<span class="badge badge-ok">✓</span>`:`<span class="badge badge-no">✗</span>`;
        const tr=document.createElement('tr'); tr.innerHTML=`<td>${x.month_year}</td><td>${s}</td><td>${sc}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadTrackerCSV(){
      const ac=document.getElementById('trk_agent').value.trim();
      if(!ac) return;
      window.open(`/api/superuser/uploads/tracker.csv?agent_code=${encodeURIComponent(ac)}&months_back=36`, '_blank');
    }

    async function loadStatements(){
      const params=new URLSearchParams();
      const ac=document.getElementById('stmt_agent').value.trim();
      const mm=document.getElementById('stmt_month').value;
      const po=document.getElementById('stmt_policy').value.trim();
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      const r=await fetch(`/api/superuser/statements?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('stmt_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="9" class="text-muted text-center">No data</td></tr>';
      rows.forEach(s=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${s.statement_id}</td><td>${s.agent_code||''}</td><td>${s.policy_no||''}</td>
          <td>${s.holder||''}</td><td>${s.policy_type||''}</td><td>${s.pay_date||''}</td>
          <td>${s.premium||''}</td><td>${s.com_amt||''}</td><td>${s.month_year || s.MONTH_YEAR || ''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadStatementsCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('stmt_agent').value.trim();
      const mm=document.getElementById('stmt_month').value;
      const po=document.getElementById('stmt_policy').value.trim();
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      window.open(`/api/admin/statements.csv?${params.toString()}`,'_blank');
    }

    async function loadSchedules(){
      const params=new URLSearchParams();
      const ac=document.getElementById('sch_agent').value.trim();
      const mm=document.getElementById('sch_month').value;
      const lo=document.getElementById('sch_latest').value || '1';
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(ac) params.append('latest_only',lo);
      const r=await fetch(`/api/superuser/schedule?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('sch_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>';
      rows.forEach(sc=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${sc.schedule_id}</td><td>${sc.agent_code||''}</td><td>${sc.commission_batch_code||''}</td>
          <td>${sc.total_premiums||''}</td><td>${sc.income||''}</td><td>${sc.total_deductions||''}</td>
          <td>${sc.net_commission||''}</td><td>${sc.month_year||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadSchedulesCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('sch_agent').value.trim();
      const mm=document.getElementById('sch_month').value;
      const lo=document.getElementById('sch_latest').value || '1';
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(ac) params.append('latest_only',lo);
      window.open(`/api/admin/schedule.csv?${params.toString()}`,'_blank');
    }

    async function loadTerminated(){
      const params=new URLSearchParams();
      const ac=document.getElementById('ter_agent').value.trim();
      const mm=document.getElementById('ter_month').value;
      const po=document.getElementById('ter_policy').value.trim();
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      const r=await fetch(`/api/superuser/terminated?${params.toString()}`,{headers:headers()} );
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('ter_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>';
      rows.forEach(t=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${t.terminated_id}</td><td>${t.agent_code||''}</td><td>${t.policy_no||''}</td>
          <td>${t.holder||''}</td><td>${t.status||''}</td><td>${t.reason||''}</td>
          <td>${t.month_year||''}</td><td>${t.termination_date||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadTerminatedCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('ter_agent').value.trim();
      const mm=document.getElementById('ter_month').value;
      const po=document.getElementById('ter_policy').value.trim();
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      window.open(`/api/admin/terminated.csv?${params.toString()}`,'_blank');
    }

    async function loadActivePolicies(){
      const params=new URLSearchParams();
      const ac=document.getElementById('ap_agent').value.trim();
      const mm=document.getElementById('ap_month').value;
      const st=document.getElementById('ap_status').value;
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(st) params.append('status',st);
      const r=await fetch(`/api/superuser/active-policies?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('active_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>';
      rows.forEach(a=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${a.id}</td><td>${a.agent_code||''}</td><td>${a.policy_no||''}</td><td>${a.policy_type||''}</td>
          <td>${a.holder_name||''}</td><td>${a.last_seen_month_year||''}</td><td>${a.last_premium||''}</td><td>${a.status||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadActivePoliciesCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('ap_agent').value.trim();
      const mm=document.getElementById('ap_month').value;
      const st=document.getElementById('ap_status').value;
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(st) params.append('status',st);
      window.open(`/api/admin/active-policies.csv?${params.toString()}`,'_blank');
    }

    async function loadMissing(){
      const ac=document.getElementById('mp_agent').value.trim();
      const mm=document.getElementById('mp_month').value;
      if(!ac || !mm) return;
      const r = await fetch(`/api/superuser/missing?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(mm)}`,{headers:headers()});
      const j = await r.json();
      const rows = j.items || [];
      const tb = document.getElementById('missing_tbody');
      tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="3" class="text-muted text-center">No missing policies</td></tr>';
      rows.forEach(m=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `<td>${m.policy_no||''}</td><td>${m.last_seen_month||''}</td><td>${m.last_premium||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadMissingCSV(){
      const ac=document.getElementById('mp_agent').value.trim();
      const mm=document.getElementById('mp_month').value;
      if(!ac || !mm) return;
      window.open(`/api/superuser/missing.csv?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(mm)}`,'_blank');
    }

    async function loadAuditFlags(){
      const params=new URLSearchParams();
      const ac=document.getElementById('af_agent').value.trim();
      const mm=document.getElementById('af_month').value;
      const rs=document.getElementById('af_resolved').value;
      if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(rs) params.append('resolved',rs);
      const r=await fetch(`/api/superuser/audit-flags?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('audit_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No flags</td></tr>';
      rows.forEach(a=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${a.id}</td><td>${a.agent_code||''}</td><td>${a.policy_no||''}</td><td>${a.month_year||''}</td>
          <td>${a.flag_type||''}</td><td>${a.severity||''}</td><td>${a.flag_detail||''}</td><td>${a.resolved ? 'true':'false'}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadAuditFlagsCSV(){
      const params=new URLSearchParams();
      const ac=document.getElementById('af_agent').value.trim();
      const mm=document.getElementById('af_month').value;
      const rs=document.getElementById('af_resolved').value;
      if(ac) params.append('agent_code', ac); if(mm) params.append('month_year', mm); if(rs) params.append('resolved', rs);
      window.open(`/api/superuser/audit-flags.csv?${params.toString()}`,'_blank');
    }

    async function generateMonthlyAgentMonth(){
      const ac=document.getElementById('mr_agent').value.trim();
      const mm=document.getElementById('mr_month').value;
      const an=document.getElementById('mr_agent_name').value.trim();
      const uid=document.getElementById('mr_user_id').value.trim();
      const upid=document.getElementById('mr_upload_id').value.trim();
      const out=document.getElementById('mr_out').value.trim();

      const fd=new FormData();
      if(ac) fd.append('agent_code', ac);
      fd.append('month_year', mm);
      if (an)  fd.append('agent_name', an);
      if (uid) fd.append('user_id', uid);
      if (upid)fd.append('upload_id', upid);
      fd.append('out', out);

      const r=await fetch('/api/admin/reports/generate-agent-month',{method:'POST', body:fd});
      const j=await r.json();
      const el=document.getElementById('mr_result');
      el.innerHTML = `
        <div class="alert alert-success">
          <div><strong>Status:</strong> ${j.status || 'UNKNOWN'}</div>
          <div><strong>Agent:</strong> ${j.agent_code || ac} &nbsp; (${j.agent_name || an || ac})</div>
          <div><strong>Month:</strong> ${j.month_year || mm}</div>
          <div><strong>Report period:</strong> ${j.report_period || ''}</div>
          <div><strong>Upload used:</strong> ${j.upload_id_used ?? j.upload_id ?? ''}</div>
          <div><strong>Expected rows inserted:</strong> ${j.expected_rows_inserted ?? 0}</div>
          <div><strong>PDF:</strong> ${(j.pdf && j.pdf.pdf_path) ? j.pdf.pdf_path : 'generated'}</div>
        </div>
        <pre class="code">${JSON.stringify(j, null, 2)}</pre>`;
    }

    (function init(){ populateMonthSelects(); })();
  </script>
</body>
</html>
    """.strip()
    return HTMLResponse(html)
