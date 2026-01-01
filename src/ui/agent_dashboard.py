
# src/ui/agent_dashboard.py
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Agent Dashboard"])

@router.get("/ui/agent", response_class=HTMLResponse)
async def agent_dashboard():
    html = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Agent Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
  <style>
    :root{
      --bg:#0b0b1a; --panel:#111130; --accent:#20c997; --accent-2:#6c5ce7; --accent-3:#ffd166; --accent-4:#ff6b6b;
      --ok:#10b981; --danger:#ef4444; --muted:#9ca3af; --text:#e5e7eb; --white:#ffffff;
    }
    body { background:radial-gradient(1200px 600px at 10% 10%, #12122a 0%, #0b0b1a 60%); color:var(--text); }
    a, a:hover { color: var(--accent); text-decoration: none; }
    .sidebar { width:300px; position:fixed; top:0; left:0; bottom:0; background:linear-gradient(180deg,#111130,#0b0b1a); color:#fff; padding:22px; overflow-y:auto; }
    .nav-link { color:rgba(255,255,255,.92); cursor:pointer; padding:8px 12px; display:block; }
    .nav-link.active, .nav-link:hover { background:linear-gradient(90deg, rgba(32,201,151,.20), rgba(108,92,231,.20)); border-left:3px solid var(--accent); border-radius:.35rem; }
    main { margin-left:300px; padding:28px; }
    .panel { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.09); border-radius:16px; padding:18px; box-shadow: 0 10px 24px rgba(0,0,0,.25); }
    .toolbar { display:flex; gap:8px; align-items:center; justify-content:space-between; }
    .badge-ok { background: var(--ok); }
    .badge-no { background: var(--danger); }
    .text-kicker { text-transform:uppercase; font-size:.76rem; color:var(--muted); letter-spacing:.08em; }
    .btn-accent { background: var(--accent); color: var(--white); }
    .btn-outline-accent { border-color: var(--accent); color: var(--accent); }
    .btn-outline-accent:hover { background: var(--accent); color: var(--white); }
    select.form-select, input.form-control { background:#0f1b33; color:#dbeafe; border:1px solid #1f2937; }
    .section { display:none; }
    .section.active { display:block; }
    .cards { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; }
    .cardx { border-radius:14px; padding:16px; color:#fff; }
    .c1 { background:linear-gradient(135deg, #20c997 0%, #4ade80 100%); }
    .c2 { background:linear-gradient(135deg, #6c5ce7 0%, #a78bfa 100%); }
    .c3 { background:linear-gradient(135deg, #ff6b6b 0%, #fca5a5 100%); }
    .c4 { background:linear-gradient(135deg, #ffd166 0%, #f59e0b 100%); }
    .cardx .label { font-size:.8rem; opacity:.9; }
    .cardx .value { font-size:1.6rem; font-weight:700; }
    .id-box { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); padding:10px; border-radius:10px; margin-bottom:10px; }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div class="d-flex align-items-center mb-3">
      <i class="bi bi-person-circle me-2" style="color:var(--accent)"></i>
      <h5 class="mb-0">Agent Dashboard</h5>
    </div>

    <div class="mb-3">
      <a href="/ui/" class="nav-link"><i class="bi bi-house me-2"></i>Landing</a>
      <a href="/ui/admin" class="nav-link"><i class="bi bi-gear me-2"></i>Admin Dashboard</a>
      <a href="/ui/superuser" class="nav-link"><i class="bi bi-shield-lock me-2"></i>Superuser Dashboard</a>
      <a class="nav-link" onclick="logout()"><i class="bi bi-box-arrow-right me-2"></i>Logout</a>
    </div>

    <div class="text-kicker mb-1">Overview</div>
    <a class="nav-link active" onclick="showSection('summary',event); loadSummary();"><i class="bi bi-activity me-2"></i>Summary</a>

    <div class="text-kicker mt-3 mb-1">Uploads</div>
    <a class="nav-link" onclick="showSection('uploads',event); loadUploads();"><i class="bi bi-cloud-arrow-up me-2"></i>Uploads</a>
    <a class="nav-link" onclick="showSection('tracker',event); loadTracker();"><i class="bi bi-check2-circle me-2"></i>Upload Tracker</a>

    <div class="text-kicker mt-3 mb-1">Data Explorer</div>
    <a class="nav-link" onclick="showSection('statements',event); loadStatements();"><i class="bi bi-file-text me-2"></i>Statements</a>
    <a class="nav-link" onclick="showSection('schedules',event); loadSchedules();"><i class="bi bi-calendar3 me-2"></i>Schedules</a>
    <a class="nav-link" onclick="showSection('terminated',event); loadTerminated();"><i class="bi bi-x-circle me-2"></i>Terminated</a>
    <a class="nav-link" onclick="showSection('activepol',event); loadActivePolicies();"><i class="bi bi-shield-shaded me-2"></i>Active Policies</a>
    <a class="nav-link" onclick="showSection('missingpol',event); loadMissing();"><i class="bi bi-search me-2"></i>Missing Policies</a>

    <div class="text-kicker mt-3 mb-1">Reports</div>
    <a class="nav-link" onclick="showSection('monthly',event);"><i class="bi bi-diagram-3 me-2"></i>Monthly Reports</a>
  </aside>

  <main>
    <div class="id-box">
      <div class="small text-muted">Identity headers for Agent wrapper APIs (stored in localStorage).</div>
      <div class="row g-2">
        <div class="col-md-4"><input id="id_email" class="form-control" placeholder="x-user-email"></div>
        <div class="col-md-4"><input id="id_role" class="form-control" placeholder="x-user-role (agent)" value="agent"></div>
        <div class="col-md-4"><input id="id_agent" class="form-control" placeholder="x-user-agent (your agent_code)"></div>
        <div class="col-md-12 d-flex justify-content-end"><button class="btn btn-outline-accent btn-sm" onclick="saveIdentity()">Save identity</button></div>
      </div>
    </div>

    <!-- Summary -->
    <section id="summary" class="panel section active">
      <div class="toolbar">
        <h4 class="mb-0">Agent Summary</h4>
        <div class="small text-muted">Snapshot for the authenticated agent.</div>
      </div>
      <div id="agent_identity" class="mt-2 small"></div>
      <div class="cards mt-3">
        <div class="cardx c1">
          <div class="label">Active Policies</div>
          <div class="value" id="sum_active_policies">0</div>
        </div>
        <div class="cardx c2">
          <div class="label">Active Statements</div>
          <div class="value" id="sum_active_statements">0</div>
        </div>
        <div class="cardx c3">
          <div class="label">Active Schedules</div>
          <div class="value" id="sum_active_schedules">0</div>
        </div>
        <div class="cardx c4">
          <div class="label">Active Terminated</div>
          <div class="value" id="sum_active_terminated">0</div>
        </div>
      </div>
      <div class="mt-3">
        <div id="sum_note" class="small text-muted">Counts use active uploads and policy status via wrapper APIs.</div>
      </div>
    </section>

    <!-- Uploads -->
    <section id="uploads" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Uploads</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadUploadsCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
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
          <thead><tr><th>ID</th><th>DocType</th><th>File</th><th>Month</th><th>Timestamp</th><th>Active</th></tr></thead>
          <tbody id="up_tbody"><tr><td colspan="6" class="text-muted text-center">Enter filters and click Load</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Upload Tracker -->
    <section id="tracker" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Upload Tracker</h4>
        <div class="small text-muted">Shows last 36 months (active uploads only).</div>
      </div>
      <div class="table-responsive mt-2">
        <table class="table table-sm table-dark table-hover">
          <thead><tr><th>Month</th><th>Statement</th><th>Schedule</th></tr></thead>
          <tbody id="trk_tbody"><tr><td colspan="3" class="text-muted text-center">Loading...</td></tr></tbody>
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
        <div class="col-md-3"><label class="form-label">Month</label><select id="stmt_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Policy No</label><input id="stmt_policy" class="form-control"></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadStatements()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="statements_table">
          <thead><tr>
            <th>ID</th><th>Policy</th><th>Holder</th><th>Type</th><th>Pay Date</th>
            <th>Premium</th><th>Commission</th><th>Month</th>
          </tr></thead>
          <tbody id="stmt_tbody"><tr><td colspan="8" class="text-muted text-center">Click Load</td></tr></tbody>
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
        <div class="col-md-3"><label class="form-label">Month</label><select id="sch_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Latest Only</label><select id="sch_latest" class="form-select"><option value="1" selected>Yes</option><option value="0">No</option></select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadSchedules()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="schedules_table">
          <thead><tr>
            <th>ID</th><th>Batch</th><th>Total Premium</th><th>Income</th><th>Deductions</th><th>Net Commission</th><th>Month</th>
          </tr></thead>
          <tbody id="sch_tbody"><tr><td colspan="7" class="text-muted text-center">Click Load</td></tr></tbody>
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
        <div class="col-md-3"><label class="form-label">Month</label><select id="ter_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Policy No</label><input id="ter_policy" class="form-control"></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadTerminated()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="terminated_table">
          <thead><tr><th>ID</th><th>Policy</th><th>Holder</th><th>Status</th><th>Reason</th><th>Month</th><th>Termination Date</th></tr></thead>
          <tbody id="ter_tbody"><tr><td colspan="7" class="text-muted text-center">Click Load</td></tr></tbody>
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
        <div class="col-md-3"><label class="form-label">Last Seen Month</label><select id="ap_month" class="form-select"></select></div>
        <div class="col-md-3"><label class="form-label">Status</label>
          <select id="ap_status" class="form-select"><option value="">- status -</option><option value="ACTIVE">ACTIVE</option><option value="MISSING">MISSING</option><option value="LAPSED">LAPSED</option><option value="TERMINATED">TERMINATED</option></select>
        </div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadActivePolicies()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="active_table">
          <thead><tr><th>ID</th><th>Policy</th><th>Type</th><th>Holder</th><th>Last Seen</th><th>Premium</th><th>Status</th></tr></thead>
          <tbody id="active_tbody"><tr><td colspan="7" class="text-muted text-center">Click Load</td></tr></tbody>
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
        <div class="col-md-3"><label class="form-label">Month</label><select id="mp_month" class="form-select"></select></div>
        <div class="col-md-3 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadMissing()">Load</button></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-dark table-hover" id="missing_table">
          <thead><tr><th>Policy</th><th>Last Seen Month</th><th>Last Premium</th></tr></thead>
          <tbody id="missing_tbody"><tr><td colspan="3" class="text-muted text-center">Select month</td></tr></tbody>
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
    // -------- Identity headers for wrapper APIs --------
    function saveIdentity(){
      localStorage.setItem('id_email', document.getElementById('id_email').value.trim());
      localStorage.setItem('id_role',  document.getElementById('id_role').value.trim());
      localStorage.setItem('id_agent', document.getElementById('id_agent').value.trim()); // must be set for agent
      alert('Identity saved. Requests will include x-user-* headers.');
      loadSummary();
      loadTracker();
    }
    function headers(){
      return {
        'x-user-email': localStorage.getItem('id_email') || '',
        'x-user-role':  localStorage.getItem('id_role')  || 'agent',
        'x-user-agent': localStorage.getItem('id_agent') || ''
      };
    }
    function logout(){ try{ localStorage.clear(); sessionStorage.clear(); }catch(e){} window.location.href = "/ui/"; }

    // -------- Section switcher --------
    function showSection(id, ev){
      document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));
      let target = null;
      if (ev) { try { if (ev.target) target = ev.target.closest ? ev.target.closest('.nav-link') : null; else if (ev.classList && ev.classList.contains && ev.classList.contains('nav-link')) target = ev; } catch (e) { target = null; } }
      if (target && target.classList) target.classList.add('active');
      document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
      const sec = document.getElementById(id); if (sec) sec.classList.add('active');
    }

    // -------- Month labels --------
    function generateMonths(n=36){
      const out=[], abbr=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const now=new Date(); let y=now.getFullYear(), m=now.getMonth();
      for(let i=0;i<n;i++){ const mm=(m-i); const year=y+Math.floor(mm/12); const mon=((mm%12)+12)%12; out.push(`${abbr[mon]} ${year}`); }
      return out;
    }
    function populateMonthSelects(){
      const labels=generateMonths(36);
      ['up_month','stmt_month','sch_month','ter_month','ap_month','mp_month','mr_month']
        .forEach(id=>{ const el=document.getElementById(id); if(!el) return; el.innerHTML=''; labels.forEach(l=>{ const opt=document.createElement('option'); opt.value=l; opt.textContent=l; el.appendChild(opt); }); });
    }

    // -------- Summary --------
    async function loadSummary(){
      const idAgent = localStorage.getItem('id_agent') || '';
      const idEmail  = localStorage.getItem('id_email') || '';
      if(!idAgent){
        document.getElementById('agent_identity').innerHTML = '<div class="text-danger">Set identity — agent_code required.</div>';
        return;
      }
      // Show identity
      document.getElementById('agent_identity').innerHTML =
        `<div class="alert alert-secondary" style="background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.15)">
          <div><strong>Email:</strong> ${idEmail}</div>
          <div><strong>Agent:</strong> ${idAgent}</div>
        </div>`;

      // Active policies count
      const rAP=await fetch(`/api/agent/active-policies?status=ACTIVE&limit=100000`,{headers:headers()});
      const jAP=await rAP.json(); const itemsAP=jAP.items || [];
      document.getElementById('sum_active_policies').textContent = itemsAP.length;

      // Active uploads by doc_type
      const rUP=await fetch(`/api/agent/uploads?limit=100000`,{headers:headers()});
      const jUP=await rUP.json(); const itemsUP=jUP.items || [];
      const activeUP = itemsUP.filter(u=>u.is_active);
      const cntStmt = activeUP.filter(u=>u.doc_type==='STATEMENT').length;
      const cntSch  = activeUP.filter(u=>u.doc_type==='SCHEDULE').length;
      const cntTer  = activeUP.filter(u=>u.doc_type==='TERMINATED').length;
      document.getElementById('sum_active_statements').textContent = cntStmt;
      document.getElementById('sum_active_schedules').textContent  = cntSch;
      document.getElementById('sum_active_terminated').textContent = cntTer;
    }

    // -------- Uploads --------
    async function loadUploads(){
      const params=new URLSearchParams();
      const mm=document.getElementById('up_month').value;
      const dt=document.getElementById('up_doc').value;
      if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt);
      const r=await fetch(`/api/agent/uploads?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('up_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="6" class="text-muted text-center">No uploads</td></tr>';
      rows.forEach(u=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${u.UploadID}</td><td>${u.doc_type||''}</td><td>${u.FileName||''}</td>
          <td>${u.month_year||''}</td><td>${u.UploadTimestamp||''}</td><td>${u.is_active?'1':'0'}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadUploadsCSV(){
      const params=new URLSearchParams();
      const mm=document.getElementById('up_month').value;
      const dt=document.getElementById('up_doc').value;
      if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt);
      window.open(`/api/admin/uploads.csv?${params.toString()}`,'_blank'); // CSV via admin export
    }

    // -------- Tracker --------
    async function loadTracker(){
      const r=await fetch(`/api/agent/uploads/tracker?months_back=36`,{headers:headers()});
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

    // -------- Statements --------
    async function loadStatements(){
      const params=new URLSearchParams();
      const mm=document.getElementById('stmt_month').value;
      const po=document.getElementById('stmt_policy').value.trim();
      if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      const r=await fetch(`/api/agent/statements?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('stmt_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>';
      rows.forEach(s=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${s.statement_id}</td><td>${s.policy_no||''}</td>
          <td>${s.holder||''}</td><td>${s.policy_type||''}</td><td>${s.pay_date||''}</td>
          <td>${s.premium||''}</td><td>${s.com_amt||''}</td><td>${s.MONTH_YEAR||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadStatementsCSV(){
      const params=new URLSearchParams();
      const mm=document.getElementById('stmt_month').value;
      const po=document.getElementById('stmt_policy').value.trim();
      if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      window.open(`/api/admin/statements.csv?${params.toString()}`,'_blank'); // CSV via admin export
    }

    // -------- Schedules --------
    async function loadSchedules(){
      const params=new URLSearchParams();
      const mm=document.getElementById('sch_month').value;
      const lo=document.getElementById('sch_latest').value || '1';
      if(mm) params.append('month_year',mm);
      params.append('latest_only', lo);  // agent wrapper dedup by month when latest_only=1
      const r=await fetch(`/api/agent/schedule?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('sch_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="7" class="text-muted text-center">No data</td></tr>';
      rows.forEach(sc=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${sc.schedule_id}</td><td>${sc.commission_batch_code||''}</td>
          <td>${sc.total_premiums||''}</td><td>${sc.income||''}</td><td>${sc.total_deductions||''}</td>
          <td>${sc.net_commission||''}</td><td>${sc.month_year||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadSchedulesCSV(){
      const params=new URLSearchParams();
      const mm=document.getElementById('sch_month').value;
      const lo=document.getElementById('sch_latest').value || '1';
      if(mm) params.append('month_year',mm); params.append('latest_only', lo);
      window.open(`/api/admin/schedule.csv?${params.toString()}`,'_blank'); // CSV via admin export
    }

    // -------- Terminated --------
    async function loadTerminated(){
      const params=new URLSearchParams();
      const mm=document.getElementById('ter_month').value;
      const po=document.getElementById('ter_policy').value.trim();
      if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      const r=await fetch(`/api/agent/terminated?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('ter_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="7" class="text-muted text-center">No data</td></tr>';
      rows.forEach(t=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${t.terminated_id}</td><td>${t.policy_no||''}</td>
          <td>${t.holder||''}</td><td>${t.status||''}</td><td>${t.reason||''}</td>
          <td>${t.month_year||''}</td><td>${t.termination_date||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadTerminatedCSV(){
      const params=new URLSearchParams();
      const mm=document.getElementById('ter_month').value;
      const po=document.getElementById('ter_policy').value.trim();
      if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po);
      window.open(`/api/admin/terminated.csv?${params.toString()}`,'_blank'); // CSV via admin export
    }

    // -------- Active Policies --------
    async function loadActivePolicies(){
      const params=new URLSearchParams();
      const mm=document.getElementById('ap_month').value;
      const st=document.getElementById('ap_status').value;
      if(mm) params.append('month_year',mm); if(st) params.append('status',st);
      const r=await fetch(`/api/agent/active-policies?${params.toString()}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('active_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="7" class="text-muted text-center">No data</td></tr>';
      rows.forEach(a=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `
          <td>${a.id}</td><td>${a.policy_type||''}</td>
          <td>${a.holder_name||''}</td><td>${a.last_seen_month_year||''}</td><td>${a.last_premium||''}</td><td>${a.status||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadActivePoliciesCSV(){
      const params=new URLSearchParams();
      const mm=document.getElementById('ap_month').value;
      const st=document.getElementById('ap_status').value;
      if(mm) params.append('month_year',mm); if(st) params.append('status',st);
      window.open(`/api/admin/active-policies.csv?${params.toString()}`,'_blank'); // CSV via admin export
    }

    // -------- Missing --------
    async function loadMissing(){
      const mm=document.getElementById('mp_month').value;
      if(!mm) return;
      const r=await fetch(`/api/agent/missing?month_year=${encodeURIComponent(mm)}`,{headers:headers()});
      const j=await r.json(); const rows=j.items||[];
      const tb=document.getElementById('missing_tbody'); tb.innerHTML='';
      if(!rows.length) tb.innerHTML='<tr><td colspan="3" class="text-muted text-center">No missing policies</td></tr>';
      rows.forEach(m=>{
        const tr=document.createElement('tr');
        tr.innerHTML = `<td>${m.policy_no||''}</td><td>${m.last_seen_month||''}</td><td>${m.last_premium||''}</td>`;
        tb.appendChild(tr);
      });
    }
    function downloadMissingCSV(){
      const mm=document.getElementById('mp_month').value;
      if(!mm) return;
      window.open(`/api/admin/missing.csv?month_year=${encodeURIComponent(mm)}`,'_blank'); // CSV via admin export
    }

    // -------- Monthly report --------
    async function generateMonthlyAgentMonth(){
      const idAgent = localStorage.getItem('id_agent') || '';
      const mm=document.getElementById('mr_month').value;
      const an=document.getElementById('mr_agent_name').value.trim();
      const uid=document.getElementById('mr_user_id').value.trim();
      const upid=document.getElementById('mr_upload_id').value.trim();
      const out=document.getElementById('mr_out').value.trim();

      const fd=new FormData();
      fd.append('agent_code', idAgent);
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
          <div><strong>Agent:</strong> ${j.agent_code || idAgent} &nbsp; (${j.agent_name || an || idAgent})</div>
          <div><strong>Month:</strong> ${j.month_year || mm}</div>
          <div><strong>Report period:</strong> ${j.report_period || ''}</div>
          <div><strong>Upload used:</strong> ${j.upload_id_used ?? j.upload_id ?? ''}</div>
          <div><strong>Expected rows inserted:</strong> ${j.expected_rows_inserted ?? 0}</div>
          <div><strong>PDF:</strong> ${(j.pdf && j.pdf.pdf_path) ? j.pdf.pdf_path : 'generated'}</div>
        </div>
        <pre class="code">${JSON.stringify(j, null, 2)}</pre>`;
    }

    // -------- Bootstrap --------
    (function init(){ populateMonthSelects(); loadSummary(); loadTracker(); })();
  </script>
</body>
</html>
    """.strip()
    return HTMLResponse(html)
