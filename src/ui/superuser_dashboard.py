
# src/ui/superuser_dashboard.py
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui/superuser", tags=["Superuser Dashboard · Midnight Plum"])

@router.get("/", response_class=HTMLResponse)
def superuser_dashboard() -> HTMLResponse:
    return HTMLResponse(_super_html())

def _super_html() -> str:
    # Midnight-plum theme; parity with Admin (minus Docs/Manage tabs). Uses /api/superuser/*
    return r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Superuser Dashboard · ICRS · Midnight Plum</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet"/>
  <style>
    :root{
      --bg:#020617; --bg-panel:#020617; --bg-main:#020617;
      --text:#e5e7eb; --text-muted:#9ca3af;
      --accent:#a855f7; --accent2:#22c55e; --accent-soft:rgba(168,85,247,.16);
      --border:#1f2937; --border-strong:#0f172a;
    }
    *{box-sizing:border-box}
    body{
      margin:0; min-height:100vh; color:var(--text);
      font-family:system-ui,-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;
      background:
        radial-gradient(circle at top left,#a855f733 0,transparent 55%),
        radial-gradient(circle at bottom right,#22c55e22 0,transparent 55%),
        radial-gradient(circle at center,#0f172a 0,#020617 60%);
    }
    .shell{max-width:1440px;margin:0 auto;padding:18px}
    .shell-inner{display:flex;gap:18px}
    .left-nav{
      width:260px;background:rgba(15,23,42,.96);border-radius:18px;padding:16px 14px;
      border:1px solid rgba(109,40,217,.55);
      box-shadow:0 28px 80px rgba(0,0,0,.9),0 0 0 1px rgba(15,23,42,.8);
    }
    .brand-title{font-weight:600;letter-spacing:.12em;text-transform:uppercase;font-size:11px;display:flex;align-items:center;gap:8px}
    .brand-title i{color:var(--accent);font-size:18px}
    .brand-pill{font-size:10px;padding:2px 7px;border-radius:999px;border:1px solid rgba(148,163,184,.7);color:var(--text-muted);text-transform:uppercase;letter-spacing:.14em}
    .idcard{
      border-radius:12px;border:1px solid #1f2937;
      background:radial-gradient(circle at top left,#0f172a 0,transparent 65%),
                 radial-gradient(circle at bottom right,#0b1120 0,transparent 60%);
      font-size:12px;color:var(--text-muted);
    }
    .nav-pills .nav-link{
      border-radius:10px;font-size:13px;color:var(--text-muted);padding:7px 8px;display:flex;align-items:center;gap:8px;border:1px solid transparent;margin-bottom:2px;background:transparent;cursor:pointer
    }
    .nav-pills .nav-link i{font-size:16px;color:#4b5563}
    .nav-pills .nav-link:hover{background:rgba(15,23,42,.95);color:#e5e7eb}
    .nav-pills .nav-link.active{
      background:
        radial-gradient(circle at left,#a855f733 0,transparent 70%),
        radial-gradient(circle at right,#22c55e22 0,transparent 70%);
      color:#f9fafb;border-color:rgba(168,85,247,.7);
      box-shadow:0 0 0 1px rgba(34,197,94,.45),0 0 20px rgba(8,47,73,.7)
    }
    .nav-pills .nav-link.active i{color:var(--accent)}

    .main{
      flex:1;min-width:0;background:rgba(15,23,42,.94);border-radius:18px;padding:14px;border:1px solid var(--border);
      box-shadow:0 30px 80px rgba(0,0,0,.9)
    }
    .section{display:none}.section.active{display:block}

    .card{
      border-radius:16px;border:1px solid var(--border);
      background:radial-gradient(circle at top left,#0f172a 0,transparent 60%),
                 radial-gradient(circle at bottom right,#020617 0,transparent 60%),#020617;
      box-shadow:0 18px 60px rgba(0,0,0,.9)
    }
    .card h6{font-size:14px;letter-spacing:.12em;text-transform:uppercase;color:#e5e7eb}
    .small{font-size:.84rem;color:var(--text-muted)}
    .table{color:#e5e7eb}
    .table thead th{white-space:nowrap;font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#9ca3af;border-bottom-color:#1f2937}
    .table tbody td{font-size:12px;vertical-align:middle;border-top-color:#111827}

    label.form-label{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:#9ca3af;margin-bottom:2px}
    .form-control,.form-select{border-radius:999px;font-size:12px;border:1px solid #374151;padding:6px 10px;background:#020617;color:#f9fafb}
    .form-control::placeholder{color:#4b5563}.form-select option{background:#020617;color:#f9fafb}
    .btn{border-radius:999px;font-size:12px}
    .btn-primary{background:radial-gradient(circle at top left,#a855f7 0,#22c55e 70%);border:none}
    .btn-outline-secondary{border-color:#4b5563;color:#e5e7eb}.btn-outline-secondary:hover{background:#111827}
    .btn-warning{background:#f59e0b;border:none;color:#0f172a}
    .badge-soft{border-radius:999px;font-size:10px;padding:2px 8px;background:var(--accent-soft);color:#e0f2fe;text-transform:uppercase;letter-spacing:.14em}
    .mono{font-family:ui-monospace,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace}
    #rp_msg,#pf_msg{border-radius:10px;border:1px solid #374151}
  </style>
</head>
<body>
<div class="shell">
  <div class="shell-inner">
    <!-- LEFT NAV -->
    <div class="left-nav">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <div class="brand-title">
          <i class="bi bi-stars"></i>
          <span>ICRS SUPERUSER</span>
        </div>
        <span class="brand-pill">v1.0</span>
      </div>
      <div class="d-flex justify-content-end align-items-center mb-2">
        <a class="btn btn-outline-danger btn-sm" href="/api/auth/logout"><i class="bi bi-box-arrow-right me-1"></i>Logout</a>
      </div>

      <div id="idcard" class="idcard py-2 px-3 mb-3">Verifying access…</div>

      <div class="nav flex-column nav-pills">
        <a class="nav-link active" onclick="show('uploadpdf')"><i class="bi bi-cloud-upload"></i><span>Upload PDF</span></a>
        <a class="nav-link" onclick="show('uploads')"><i class="bi bi-cloud-arrow-up"></i><span>Uploads</span></a>
        <a class="nav-link" onclick="show('statements')"><i class="bi bi-receipt"></i><span>Statements</span></a>
        <a class="nav-link" onclick="show('schedule')"><i class="bi bi-table"></i><span>Schedule</span></a>
        <a class="nav-link" onclick="show('terminated')"><i class="bi bi-slash-circle"></i><span>Terminated</span></a>
        <a class="nav-link" onclick="show('activepolicies')"><i class="bi bi-activity"></i><span>Active Policies</span></a>
        <a class="nav-link" onclick="show('missing')"><i class="bi bi-question-circle"></i><span>Missing Policies</span></a>
        <a class="nav-link" onclick="show('auditflags')"><i class="bi bi-flag"></i><span>Audit Flags</span></a>
        <a class="nav-link" onclick="show('reports')"><i class="bi bi-graph-up-arrow"></i><span>Monthly Report</span></a>
        <a class="nav-link" onclick="show('tracker')"><i class="bi bi-calendar-week"></i><span>Uploads Tracker</span></a>
      </div>
    </div>

    <!-- MAIN CONTENT -->
    <div class="main">

      <!-- Upload PDF -->
      <div id="uploadpdf" class="section active">
        <div class="card p-3 mb-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div>
              <h6 class="mb-0">Upload & Ingest PDF</h6>
              <div class="small">Validate then ingest STATEMENT / SCHEDULE / TERMINATED for any agent.</div>
            </div>
          </div>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="pf_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="pf_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Document Type</label>
              <select id="pf_type" class="form-select">
                <option value="statement">STATEMENT</option>
                <option value="schedule">SCHEDULE</option>
                <option value="terminated">TERMINATED</option>
              </select>
            </div>
            <div class="col-md-3"><label class="form-label">Agent Name (optional)</label><input id="pf_name" class="form-control"></div>
          </div>
          <div class="row g-2 mt-1 align-items-end">
            <div class="col-md-6"><label class="form-label">PDF File</label><input id="pf_file" type="file" accept="application/pdf" class="form-control"></div>
            <div class="col-md-6 d-flex gap-2">
              <button class="btn btn-primary mt-4" onclick="validateAndUpload()"><i class="bi bi-shield-check me-1"></i>Validate & Upload</button>
              <button class="btn btn-outline-secondary mt-4" onclick="resetUpload()"><i class="bi bi-arrow-counterclockwise me-1"></i>Reset</button>
            </div>
          </div>
          <div id="pf_msg" class="alert d-none mt-3"></div>
          <div id="pf_result" class="mt-2"></div>
        </div>
      </div>

      <!-- Uploads -->
      <div id="uploads" class="section">
        <div class="card p-3 mb-3">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div><h6 class="mb-0">Uploads</h6><div class="small">Filter and inspect raw upload records.</div></div>
            <span class="badge-soft">Read‑only</span>
          </div>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Doc Type</label>
              <select id="up_doc_type" class="form-select">
                <option value="">(any)</option><option>STATEMENT</option><option>SCHEDULE</option><option>TERMINATED</option>
              </select>
            </div>
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="up_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="up_month" class="form-select"></select></div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadUploads()"><i class="bi bi-play-circle me-1"></i>Load</button>
              <a id="up_csv" class="btn btn-outline-secondary w-100" target="_blank"><i class="bi bi-filetype-csv me-1"></i>CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm align-middle">
              <thead><tr>
                <th>UploadID</th><th>Agent</th><th>Agent Name</th><th>Type</th><th>File</th>
                <th>Uploaded</th><th>Month</th><th>Active</th>
              </tr></thead>
              <tbody id="up_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Statements -->
      <div id="statements" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Statements</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="st_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="st_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Policy No</label><input id="st_pol" class="form-control"></div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadStatements()">Load</button>
              <a id="st_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>ID</th><th>Upload</th><th>Agent</th><th>Policy</th><th>Holder</th><th>Type</th>
                <th>Pay Date</th><th>Premium</th><th>Com Rate</th><th>Com Amt</th><th>Month</th>
              </tr></thead>
              <tbody id="st_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Schedule -->
      <div id="schedule" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Schedule</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="sc_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="sc_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Latest Only</label>
              <select id="sc_latest" class="form-select">
                <option value="">(auto)</option><option value="1">Yes</option><option value="0">No</option>
              </select>
            </div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadSchedule()">Load</button>
              <a id="sc_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>ScheduleID</th><th>UploadID</th><th>Agent</th><th>Agent Name</th><th>Batch Code</th>
                <th>Total Premiums</th><th>Income</th><th>Total Deductions</th><th>Net Commission</th><th>Month</th>
              </tr></thead>
              <tbody id="sc_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Terminated -->
      <div id="terminated" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Terminated</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="te_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="te_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Policy No</label><input id="te_pol" class="form-control"></div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadTerminated()">Load</button>
              <a id="te_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>TerminatedID</th><th>UploadID</th><th>Agent</th><th>Policy</th><th>Holder</th><th>Type</th>
                <th>Premium</th><th>Status</th><th>Reason</th><th>Month</th><th>Termination Date</th>
              </tr></thead>
              <tbody id="te_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Active Policies -->
      <div id="activepolicies" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Active Policies</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="ap_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Last Seen Month</label><select id="ap_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Status</label>
              <select id="ap_status" class="form-select"><option value="">(any)</option><option value="ACTIVE">ACTIVE</option><option value="MISSING">MISSING</option></select>
            </div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadActive()">Load</button>
              <a id="ap_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>ID</th><th>Agent</th><th>Policy</th><th>Type</th><th>Holder</th><th>Inception</th>
                <th>First Seen</th><th>Last Seen</th><th>Last Seen Month</th><th>Last Premium</th><th>Last Com Rate</th><th>Status</th><th>Missing Streak</th>
              </tr></thead>
              <tbody id="ap_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Missing Policies -->
      <div id="missing" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Missing Policies</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-4"><label class="form-label">Agent Code</label><input id="mi_agent" class="form-control"></div>
            <div class="col-md-4"><label class="form-label">Month</label><select id="mi_month" class="form-select"></select></div>
            <div class="col-md-4 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadMissing()">Load</button>
              <a id="mi_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>Policy No</th><th>Holder</th><th>Policy Type</th><th>Last Seen Month</th><th>Last Premium</th><th>Last Com Rate</th>
              </tr></thead>
              <tbody id="mi_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Audit Flags -->
      <div id="auditflags" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Audit Flags</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="af_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="af_month" class="form-select"></select></div>
            <div class="col-md-3"><label class="form-label">Flag Type</label><input id="af_type" class="form-control"></div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadAudit()">Load</button>
              <a id="af_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>Agent</th><th>Policy</th><th>Month</th><th>Type</th><th>Severity</th><th>Detail</th>
                <th>Expected</th><th>Actual</th><th>Created</th>
              </tr></thead>
              <tbody id="af_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Monthly Report -->
      <div id="reports" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-3">Generate & Download Monthly Report</h6>
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label">Agent Code</label><input id="rp_agent" class="form-control"></div>
            <div class="col-md-3"><label class="form-label">Month</label><select id="rp_month" class="form-select"></select></div>
            <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-primary w-100" onclick="generateAgentMonth()">Generate</button>
            </div>
            <div class="col-md-3 d-flex align-items-end">
              <button class="btn btn-outline-secondary w-100" onclick="downloadLatestPDF()">Download PDF</button>
            </div>
          </div>
          <div id="rp_msg" class="alert mt-3 d-none"></div>
        </div>
      </div>

      <!-- Uploads Tracker -->
      <div id="tracker" class="section">
        <div class="card p-3 mb-3">
          <h6 class="mb-2">Uploads Tracker</h6>
          <div class="row g-2 align-items-end">
            <div class="col-md-4"><label class="form-label">Agent Code</label><input id="tr_agent" class="form-control"></div>
            <div class="col-md-4"><label class="form-label">Months Back</label><input id="tr_back" class="form-control" type="number" value="36"></div>
            <div class="col-md-4 d-flex gap-2">
              <button class="btn btn-primary w-100" onclick="loadTracker()">Load</button>
              <a id="tr_csv" class="btn btn-outline-secondary w-100" target="_blank">CSV</a>
            </div>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-sm">
              <thead><tr>
                <th>Month</th><th>Statement</th><th>Schedule</th><th>Terminated</th>
                <th>Stmt UID</th><th>Sch UID</th><th>Ter UID</th>
              </tr></thead>
              <tbody id="tr_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>

    </div><!-- /main -->
  </div><!-- /shell-inner -->
</div><!-- /shell -->

<script>
/* ---------- Common UI helpers ---------- */
function show(id){
  document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById(id)?.classList.add('active');
  const links = document.querySelectorAll('.nav-link');
  links.forEach(el=>{
    if(el.getAttribute('onclick') === `show('${id}')`) el.classList.add('active');
  });
}
function monthLabels(n=36){
  const out=[], abbr=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const now=new Date(); let y=now.getFullYear(), m=now.getMonth();
  for(let i=0;i<n;i++){ const mm=(m-i); const year=y+Math.floor(mm/12); const mon=((mm%12)+12)%12; out.push(`${abbr[mon]} ${year}`); }
  return out;
}
function populateMonths(){
  const labels=monthLabels(36);
  ['pf_month','up_month','st_month','sc_month','te_month','rp_month','ap_month','mi_month','af_month'].forEach(id=>{
    const el=document.getElementById(id); if(!el) return; el.innerHTML='';
    const empty=document.createElement('option'); empty.value=''; empty.textContent='(any)'; el.appendChild(empty);
    labels.forEach(l=>{ const opt=document.createElement('option'); opt.value=l; opt.textContent=l; el.appendChild(opt); });
  });
}
populateMonths();

async function fetchJSON(url, opts={}){
  try{
    const r = await fetch(url, { credentials:'same-origin', ...opts });
    const ct = r.headers.get('content-type')||'';
    const j = ct.includes('application/json') ? await r.json() : {};
    return { ok:r.ok, status:r.status, json:j };
  }catch(e){ return { ok:false, status:0, json:{ detail:String(e) } }; }
}
function setText(id, txt){ const el=document.getElementById(id); if(el) el.textContent=txt; }

/* ---------- Auth guard (superuser only) ---------- */
async function guard(){
  const r = await fetchJSON('/api/auth/me', { method:'GET' });
  const card = document.getElementById('idcard');
  if(!r.ok || !r.json || r.json.status!=='OK' || !r.json.identity){
    window.location.href = '/ui/login/superuser'; // Option A alias
    return;
  }
  const role = (r.json.identity.role || '').toLowerCase();
  if(role!=='superuser'){ window.location.href = '/ui/login/superuser'; return; }
  const email=r.json.identity.user_email||r.json.identity.email||'', uid=r.json.identity.user_id||'';
  card.className='idcard py-2 px-3 mb-3 border border-success';
  card.innerHTML=`<strong>Role:</strong> ${role} · <strong>ID:</strong> ${uid} · <strong>Email:</strong> ${email}`;
}
guard();

/* ---------- Upload PDF (validate -> upload) ---------- */
function setPfMsg(text, kind='info'){ const m=document.getElementById('pf_msg'); m.className='alert alert-'+kind; m.textContent=text; m.classList.remove('d-none'); }
function resetUpload(){
  document.getElementById('pf_agent').value='';
  document.getElementById('pf_month').selectedIndex=0;
  document.getElementById('pf_type').value='statement';
  document.getElementById('pf_name').value='';
  document.getElementById('pf_file').value='';
  document.getElementById('pf_msg').className='alert d-none';
  document.getElementById('pf_result').innerHTML='';
}
async function validateAndUpload(){
  const agent=(document.getElementById('pf_agent').value||'').trim();
  const month=(document.getElementById('pf_month').value||'').trim();
  const dtype=(document.getElementById('pf_type').value||'statement').trim();
  const aname=(document.getElementById('pf_name').value||'').trim();
  const file=document.getElementById('pf_file').files[0];
  if(!agent || !month || !file){ setPfMsg('Agent, Month and PDF are required','warning'); return; }

  const fdv=new FormData(); fdv.append('agent_code',agent); fdv.append('month_year',month); fdv.append('file',file);
  const v = await fetch(`/api/uploads-secure/${dtype}`, { method:'POST', body:fdv, credentials:'same-origin' });
  const vj = await v.json();
  if(!v.ok){ setPfMsg(vj.detail || 'Validation failed','danger'); return; }
  setPfMsg(`Validated: ${vj.file_type} with ${vj.markers_matched} markers`, 'success');

  const fdi=new FormData(); fdi.append('agent_code',agent); fdi.append('month_year',month); fdi.append('agent_name',aname); fdi.append('file',file);
  const u = await fetch(`/api/pdf-enhanced/upload/${dtype}`, { method:'POST', body:fdi, credentials:'same-origin' });
  const uj = await u.json();
  if(!u.ok){ setPfMsg(uj.detail || 'Upload failed','danger'); return; }

  document.getElementById('pf_result').innerHTML = `
    <div class="alert alert-success">
      <div><strong>Uploaded & Ingested.</strong></div>
      <div class="mt-1"><small class="mono">upload_id=${uj.upload_id} · doc_type=${uj.doc_type} · records=${uj.records_count} · month=${uj.month_year}</small></div>
      <div class="mt-1"><small class="mono">saved_as=${uj.file_saved_as}</small></div>
    </div>`;
}

/* ---------- Uploads listing ---------- */
async function loadUploads(){
  const doc=document.getElementById('up_doc_type').value.trim();
  const agent=document.getElementById('up_agent').value.trim();
  const month=document.getElementById('up_month').value.trim();
  const url='/api/superuser/uploads?' + new URLSearchParams({doc_type:doc, agent_code:agent, month_year:month, limit:200});
  document.getElementById('up_csv').href='/api/superuser/uploads.csv?' + new URLSearchParams({doc_type:doc, agent_code:agent, month_year:month});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('up_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(u=>{
    const tr=document.createElement('tr');
    const active = (u.is_active? 'Yes':'No');
    tr.innerHTML = `<td>${u.UploadID||''}</td><td>${u.agent_code||''}</td><td>${u.AgentName||''}</td><td>${u.doc_type||''}</td>
                    <td>${u.FileName||''}</td><td>${u.UploadTimestamp||''}</td><td>${u.month_year||''}</td><td>${active}</td>`;
    tb.appendChild(tr);
  });
}

/* ---------- Statements / Schedule / Terminated ---------- */
async function loadStatements(){
  const agent=document.getElementById('st_agent').value.trim();
  const month=document.getElementById('st_month').value.trim();
  const pol=document.getElementById('st_pol').value.trim();
  const url='/api/superuser/statements?' + new URLSearchParams({agent_code:agent, month_year:month, policy_no:pol, limit:200});
  document.getElementById('st_csv').href='/api/superuser/statements.csv?' + new URLSearchParams({agent_code:agent, month_year:month, policy_no:pol});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('st_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(s=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${s.statement_id||''}</td><td>${s.upload_id||''}</td><td>${s.agent_code||''}</td><td>${s.policy_no||''}</td>
                  <td>${s.holder||''}</td><td>${s.policy_type||''}</td><td>${s.pay_date||''}</td><td>${s.premium||''}</td>
                  <td>${s.com_rate||''}</td><td>${s.com_amt||''}</td><td>${s.month_year||''}</td>`;
    tb.appendChild(tr);
  });
}
async function loadSchedule(){
  const agent=document.getElementById('sc_agent').value.trim();
  const month=document.getElementById('sc_month').value.trim();
  const latest=document.getElementById('sc_latest').value.trim();
  const url='/api/superuser/schedule?' + new URLSearchParams({agent_code:agent, month_year:month, latest_only:latest, limit:200});
  document.getElementById('sc_csv').href='/api/superuser/schedule.csv?' + new URLSearchParams({agent_code:agent, month_year:month, latest_only:latest});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('sc_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(sc=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${sc.schedule_id||''}</td><td>${sc.upload_id||''}</td><td>${sc.agent_code||''}</td><td>${sc.agent_name||''}</td>
                  <td>${sc.commission_batch_code||''}</td><td>${sc.total_premiums||''}</td><td>${sc.income||''}</td>
                  <td>${sc.total_deductions||''}</td><td>${sc.net_commission||''}</td><td>${sc.month_year||''}</td>`;
    tb.appendChild(tr);
  });
}
async function loadTerminated(){
  const agent=document.getElementById('te_agent').value.trim();
  const month=document.getElementById('te_month').value.trim();
  const pol=document.getElementById('te_pol').value.trim();
  const url='/api/superuser/terminated?' + new URLSearchParams({agent_code:agent, month_year:month, policy_no:pol, limit:200});
  document.getElementById('te_csv').href='/api/superuser/terminated.csv?' + new URLSearchParams({agent_code:agent, month_year:month, policy_no:pol});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('te_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(t=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${t.terminated_id||''}</td><td>${t.upload_id||''}</td><td>${t.agent_code||''}</td><td>${t.policy_no||''}</td>
                  <td>${t.holder||''}</td><td>${t.policy_type||''}</td><td>${t.premium||''}</td><td>${t.status||''}</td>
                  <td>${t.reason||''}</td><td>${t.month_year||''}</td><td>${t.termination_date||''}</td>`;
    tb.appendChild(tr);
  });
}

/* ---------- Active / Missing / Audit ---------- */
async function loadActive(){
  const agent=document.getElementById('ap_agent').value.trim();
  const month=document.getElementById('ap_month').value.trim();
  const status=document.getElementById('ap_status').value.trim();
  const url='/api/superuser/active-policies?' + new URLSearchParams({agent_code:agent, month_year:month, status, limit:200});
  document.getElementById('ap_csv').href='/api/superuser/active-policies.csv?' + new URLSearchParams({agent_code:agent, month_year:month, status});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('ap_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(x=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${x.id||''}</td><td>${x.agent_code||''}</td><td>${x.policy_no||''}</td><td>${x.policy_type||''}</td>
                  <td>${x.holder_name||''}</td><td>${x.inception_date||''}</td><td>${x.first_seen_date||''}</td>
                  <td>${x.last_seen_date||''}</td><td>${x.last_seen_month_year||''}</td><td>${x.last_premium||''}</td>
                  <td>${x.last_com_rate||''}</td><td>${x.status||''}</td><td>${x.consecutive_missing_months||''}</td>`;
    tb.appendChild(tr);
  });
}
async function loadMissing(){
  // Use admin endpoint allowed to superusers for richer columns
  const agent=document.getElementById('mi_agent').value.trim();
  const month=document.getElementById('mi_month').value.trim();
  const url='/api/admin/missing?' + new URLSearchParams({agent_code:agent, month_year:month});
  document.getElementById('mi_csv').href='/api/admin/missing.csv?' + new URLSearchParams({agent_code:agent, month_year:month});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('mi_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(x=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${x.policy_no||''}</td><td>${x.holder_name||''}</td><td>${x.policy_type||''}</td>
                  <td>${x.last_seen_month||''}</td><td>${x.last_premium||''}</td><td>${x.last_com_rate||''}</td>`;
    tb.appendChild(tr);
  });
}
async function loadAudit(){
  const agent=document.getElementById('af_agent').value.trim();
  const month=document.getElementById('af_month').value.trim();
  const flag=document.getElementById('af_type').value.trim();
  const url='/api/superuser/audit-flags?' + new URLSearchParams({agent_code:agent, month_year:month, flag_type:flag, limit:200});
  document.getElementById('af_csv').href='/api/superuser/audit-flags.csv?' + new URLSearchParams({agent_code:agent, month_year:month, flag_type:flag});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('af_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(a=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${a.agent_code||''}</td><td>${a.policy_no||''}</td><td>${a.month_year||''}</td>
                  <td>${a.flag_type||''}</td><td>${a.severity||''}</td><td>${a.flag_detail||''}</td>
                  <td>${a.expected_value||''}</td><td>${a.actual_value||''}</td><td>${a.created_at||''}</td>`;
    tb.appendChild(tr);
  });
}

/* ---------- Reports ---------- */
function setRpMsg(text, kind='info'){ const el=document.getElementById('rp_msg'); el.className='alert alert-'+kind; el.textContent=text; el.classList.remove('d-none'); }
async function generateAgentMonth(){
  const agent=document.getElementById('rp_agent').value.trim();
  const month=document.getElementById('rp_month').value.trim();
  if(!agent || !month){ setRpMsg('Provide Agent Code and Month','warning'); return; }
  // Admin endpoint allows superusers (require_admin_or_superuser)
  const form=new URLSearchParams(); form.append('agent_code',agent); form.append('month_year',month);
  const r=await fetch('/api/admin/reports/generate-agent-month',{
    method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:form, credentials:'same-origin'
  });
  const j=await r.json(); setRpMsg(r.ok ? 'Generated successfully' : ('Error: '+(j.detail||'unknown')), r.ok ? 'success' : 'danger');
}
async function downloadLatestPDF(){
  const agent=document.getElementById('rp_agent').value.trim();
  const month=document.getElementById('rp_month').value.trim();
  if(!agent || !month){ setRpMsg('Provide Agent Code and Month','warning'); return; }
  const list = await (await fetch(`/api/agent/reports?agent_code=${encodeURIComponent(agent)}&month_year=${encodeURIComponent(month)}`, {credentials:'same-origin'})).json();
  const items = list.items || []; if(!items.length){ setRpMsg('No report rows found','warning'); return; }
  const rid = items[0].report_id || items[0].id || items[0].ReportID;
  window.open(`/api/agent/reports/download/${encodeURIComponent(rid)}`, '_blank');
}

/* ---------- Uploads Tracker ---------- */
async function loadTracker(){
  const agent=document.getElementById('tr_agent').value.trim();
  const back=document.getElementById('tr_back').value.trim() || '36';
  if(!agent) return;
  const url='/api/superuser/uploads/tracker?' + new URLSearchParams({agent_code:agent, months_back:back});
  document.getElementById('tr_csv').href='/api/superuser/uploads/tracker.csv?' + new URLSearchParams({agent_code:agent, months_back:back});
  const r=await fetch(url, {credentials:'same-origin'}); const j=await r.json(); const tb=document.getElementById('tr_tbody'); tb.innerHTML='';
  (j.items||[]).forEach(x=>{
    const s = x.statement_present ? '✓' : '✗';
    const sc= x.schedule_present  ? '✓' : '✗';
    const te= x.terminated_present? '✓' : '✗';
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${x.month_year||''}</td><td>${s}</td><td>${sc}</td><td>${te}</td>
                  <td>${x.statement_upload_id||''}</td><td>${x.schedule_upload_id||''}</td><td>${x.terminated_upload_id||''}</td>`;
    tb.appendChild(tr);
  });
}
</script>
</body>
</html>
"""