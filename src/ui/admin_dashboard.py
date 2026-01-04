
from __future__ import annotations
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from src.api.ui_pages import _get_current_user

router = APIRouter(tags=["Admin Dashboard"])

@router.get("/ui/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # ---- Cookie-based guard ----
    u = _get_current_user(request) or {}
    role = str(u.get("role") or "").lower()
    if role not in ("admin", "superuser"):
        return RedirectResponse(url="/ui/login?role=admin", status_code=302)

    # ---- Full UI ----
    html = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Admin Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css">
  <style>
    :root{
      --bg:#0f172a; --bg-2:#111827; --panel:#0b1220; --accent:#00b894; --accent-2:#6c5ce7;
      --warn:#f59e0b; --ok:#10b981; --danger:#ef4444; --muted:#9ca3af; --text:#e5e7eb; --white:#ffffff;
    }
    body { background:linear-gradient(135deg, #0f172a 0%, #0b1220 100%); color:var(--text); }
    a, a:hover { color: var(--accent); text-decoration: none; }
    .sidebar { width:300px; position:fixed; top:0; left:0; bottom:0; background:linear-gradient(180deg,#0b1220,#111827); color:#fff; padding:22px; overflow-y:auto; }
    .nav-link { color:rgba(255,255,255,.92); cursor:pointer; padding:8px 12px; display:block; }
    .nav-link.active, .nav-link:hover { background:rgba(108,92,231,.18); border-left:3px solid var(--accent-2); border-radius:.35rem; }
    main { margin-left:300px; padding:28px; }
    .panel { background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.06); border-radius:14px; padding:18px; backdrop-filter: blur(3px); }
    .toolbar { display:flex; gap:8px; align-items:center; justify-content:space-between; }
    .badge-ok { background: var(--ok); }
    .badge-no { background: var(--danger); }
    .text-kicker { text-transform:uppercase; font-size:.76rem; color:var(--muted); letter-spacing:.08em; }
    .code { font-family: ui-monospace, Menlo, Consolas, "Courier New", monospace; }
    .btn-accent { background: var(--accent-2); color: var(--white); }
    .btn-outline-accent { border-color: var(--accent-2); color: var(--accent-2); }
    .btn-outline-accent:hover { background: var(--accent-2); color: var(--white); }
    select.form-select, input.form-control { background:#0f1b33; color:#dbeafe; border:1px solid #1f2937; }
    .section { display: none; }
    .section.active { display: block; }
    .edit-panel { background: rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); padding:12px; border-radius:10px; margin-top:12px; }

    .status-chip {
      font-size:.75rem; color:#d1d5db; background:#0f1b33; border:1px solid #1f2937;
      padding:6px 10px; border-radius:999px; display:inline-flex; align-items:center; gap:6px;
    }
    .status-chip i { color: var(--accent-2); }
  </style>
</head>
<body>
  <aside class="sidebar">
    <div class="d-flex align-items-center mb-3">
      <i class="bi bi-gear-fill me-2" style="color:var(--accent-2)"></i>
      <h5 class="mb-0">Admin Dashboard</h5>
    </div>

    <!-- Identity status chip -->
    <div class="mb-3">
      <span class="status-chip" id="identity_chip">
        <i class="bi bi-person-badge"></i>
        <span><strong>ID:</strong> <span id="chip_user_id">—</span></span>
        <span class="ms-2"><strong>Email:</strong> <span id="chip_user_email">—</span></span>
      </span>
    </div>

    <div class="mb-3">
      <a class="nav-link" href="/ui/agent"><i class="bi bi-person-circle me-2"></i>Agent Dashboard</a>
      <a class="nav-link" href="/ui/superuser"><i class="bi bi-shield-lock me-2"></i>Superuser Dashboard</a>
      <a class="nav-link" onclick="logout()"><i class="bi bi-box-arrow-right me-2"></i>Logout</a>
    </div>

    <div class="text-kicker mb-1">Management</div>
    <a class="nav-link active" onclick="showSection('agents',event)"><i class="bi bi-people me-2"></i>Agents</a>
    <a class="nav-link" onclick="showSection('users',event); loadUsers();"><i class="bi bi-person-badge me-2"></i>Users</a>

    <div class="text-kicker mt-3 mb-1">Uploads</div>
    <a class="nav-link" onclick="showSection('uploads',event); loadUploads();"><i class="bi bi-cloud-arrow-up me-2"></i>Uploads</a>
    <a class="nav-link" onclick="showSection('deactivate',event)"><i class="bi bi-shield-check me-2"></i>Deactivate Older</a>
    <a class="nav-link" onclick="showSection('tracker',event); loadTracker();"><i class="bi bi-check2-circle me-2"></i>Upload Tracker</a>

    <div class="text-kicker mt-3 mb-1">Data Explorer</div>
    <a class="nav-link" onclick="showSection('statements',event); loadStatements();"><i class="bi bi-file-text me-2"></i>Statements</a>
    <a class="nav-link" onclick="showSection('schedules',event); loadSchedules();"><i class="bi bi-calendar3 me-2"></i>Schedules</a>
    <a class="nav-link" onclick="showSection('terminated',event); loadTerminated();"><i class="bi bi-x-circle me-2"></i>Terminated</a>
    <a class="nav-link" onclick="showSection('activepol',event); loadActivePolicies();"><i class="bi bi-shield-shaded me-2"></i>Active Policies</a>
    <a class="nav-link" onclick="showSection('missingpol',event); loadMissing();"><i class="bi bi-search me-2"></i>Missing Policies</a>

    <div class="text-kicker mt-3 mb-1">Audit &amp; Reports</div>
    <a class="nav-link" onclick="showSection('audit',event); loadAuditFlags && loadAuditFlags();"><i class="bi bi-flag me-2"></i>Audit Flags</a>
    <a class="nav-link" onclick="showSection('monthly',event);"><i class="bi bi-diagram-3 me-2"></i>Monthly Reports</a>

    <div class="mt-3">
      <a class="nav-link" href="/docs" target="_blank"><i class="bi bi-journal-code me-2"></i>API Docs</a>
    </div>
  </aside>

  <main>
    <!-- Agents -->
    <section id="agents" class="panel section active">
      <div class="toolbar">
        <h4 class="mb-0">Agents</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="window.open('/api/admin/agents.csv','_blank')"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>

      <form class="row g-3 mt-2" onsubmit="event.preventDefault(); upsertAgent();">
        <div class="col-md-3"><label class="form-label">Agent Code *</label><input id="agent_code" class="form-control" required></div>
        <div class="col-md-4"><label class="form-label">Agent Name</label><input id="agent_name" class="form-control"></div>
        <div class="col-md-3"><label class="form-label">License Number</label><input id="license_number" class="form-control"></div>
        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-accent w-100">Upsert Agent</button></div>
      </form>
      <div id="agent_result" class="mt-2 small"></div>

      <div id="agent_edit_panel" class="edit-panel" style="display:none;">
        <h6 class="mb-2">Edit Agent</h6>
        <form class="row g-2" onsubmit="event.preventDefault(); submitEditAgent();">
          <div class="col-md-2"><label class="form-label">Code</label><input id="edit_agent_code" class="form-control" disabled></div>
          <div class="col-md-3"><label class="form-label">Name</label><input id="edit_agent_name" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">License</label><input id="edit_agent_license" class="form-control"></div>
          <div class="col-md-2"><label class="form-label">Active</label>
            <select id="edit_agent_active" class="form-select"><option value="1">1</option><option value="0">0</option></select>
          </div>
          <div class="col-md-2 d-flex align-items-end"><button class="btn btn-accent w-100">Save</button></div>
        </form>
        <div class="small" id="agent_edit_result"></div>
      </div>

      <div class="table-responsive mt-3">
        <table class="table table-sm table-dark table-hover" id="agents_table">
          <thead><tr><th>Code</th><th>Name</th><th>License</th><th>Active</th><th>Created</th><th>Updated</th><th>Actions</th></tr></thead>
          <tbody id="agents_tbody"><tr><td colspan="7" class="text-muted text-center">Loading...</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Users -->
    <section id="users" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Users</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="window.open('/api/admin/users.csv','_blank')"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <form class="row g-3 mt-2" onsubmit="event.preventDefault(); upsertUser();">
        <div class="col-md-3"><label class="form-label">Email *</label><input id="user_email" class="form-control" required></div>
        <div class="col-md-3"><label class="form-label">Password Hash *</label><input id="user_phash" class="form-control" placeholder="bcrypt hash" required></div>
        <div class="col-md-2"><label class="form-label">Agent</label><select id="user_agent" class="form-select"></select></div>
        <div class="col-md-2"><label class="form-label">Role</label><select id="user_role" class="form-select"><option>agent</option><option>admin</option><option>superuser</option></select></div>
        <div class="col-md-1"><label class="form-label">Active</label><select id="user_active" class="form-select"><option value="true">true</option><option value="false">false</option></select></div>
        <div class="col-md-1"><label class="form-label">Verified</label><select id="user_verified" class="form-select"><option value="false">false</option><option value="true">true</option></select></div>
        <div class="col-md-12 d-flex justify-content-end"><button class="btn btn-accent">Upsert User</button></div>
      </form>
      <div id="user_result" class="mt-2 small"></div>

      <div id="user_edit_panel" class="edit-panel" style="display:none;">
        <h6 class="mb-2">Edit User</h6>
        <form class="row g-2" onsubmit="event.preventDefault(); submitEditUser();">
          <div class="col-md-2"><label class="form-label">ID</label><input id="edit_user_id" class="form-control" disabled></div>
          <div class="col-md-3"><label class="form-label">Email</label><input id="edit_user_email" class="form-control"></div>
          <div class="col-md-3"><label class="form-label">Password Hash</label><input id="edit_user_phash" class="form-control" placeholder="optional"></div>
          <div class="col-md-2"><label class="form-label">Agent</label><select id="edit_user_agent" class="form-select"></select></div>
          <div class="col-md-2"><label class="form-label">Role</label><select id="edit_user_role" class="form-select"><option>agent</option><option>admin</option><option>superuser</option></select></div>
          <div class="col-md-2"><label class="form-label">Active</label><select id="edit_user_active" class="form-select"><option value="true">true</option><option value="false">false</option></select></div>
          <div class="col-md-2"><label class="form-label">Verified</label><select id="edit_user_verified" class="form-select"><option value="false">false</option><option value="true">true</option></select></div>
          <div class="col-md-2 d-flex align-items-end"><button class="btn btn-accent w-100">Save</button></div>
        </form>
        <div class="small" id="user_edit_result"></div>
      </div>

      <div class="table-responsive mt-3">
        <table class="table table-sm table-dark table-hover" id="users_table">
          <thead><tr><th>ID</th><th>Email</th><th>Role</th><th>Agent</th><th>Active</th><th>Verified</th><th>Last Login</th><th>Actions</th></tr></thead>
          <tbody id="users_tbody"><tr><td colspan="8" class="text-muted text-center">Loading...</td></tr></tbody>
        </table>
      </div>
    </section>

    <!-- Uploads -->
    <section id="uploads" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Uploads</h4>
        <button class="btn btn-outline-accent btn-sm" onclick="downloadUploadsCSV()"><i class="bi bi-filetype-csv"></i> CSV</button>
      </div>
      <div class="row g-2 mb-2">
        <div class="col-md-3"><label class="form-label">Agent</label><select id="up_agent" class="form-select"></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent *</label><select id="dec_agent" class="form-select" required></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="trk_agent" class="form-select"></select></div>
        <div class="col-md-2 d-flex align-items-end"><button class="btn btn-accent w-100" onclick="loadTracker()">Show</button></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="stmt_agent" class="form-select"></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="sch_agent" class="form-select"></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="ter_agent" class="form-select"></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="ap_agent" class="form-select"></select></div>
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
        <div class="col-md-3"><label class="form-label">Agent</label><select id="mp_agent" class="form-select"></select></div>
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

    <!-- Monthly Reports -->
    <section id="monthly" class="panel section">
      <div class="toolbar">
        <h4 class="mb-0">Monthly Reports</h4>
        <div class="small text-muted">Generate single-agent report by month (PDF generated; expected commissions inserted).</div>
      </div>
      <form class="row g-3 mt-2" onsubmit="event.preventDefault(); generateMonthlyAgentMonth();">
        <div class="col-md-3"><label class="form-label">Agent *</label><select id="mr_agent" class="form-select" required></select></div>
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
    let AGENTS = [];

    function getUserId(){
      try{
        const v = sessionStorage.getItem('user_id') || localStorage.getItem('user_id');
        const n = parseInt(v, 10);
        return isNaN(n) ? null : n;
      }catch(e){ return null; }
    }
    function setUserId(v){
      try{
        const n = parseInt(v, 10);
        if(!isNaN(n) && n > 0){
          sessionStorage.setItem('user_id', String(n));
          localStorage.setItem('user_id', String(n));
        }
      }catch(e){}
    }
    function getUserEmail(){
      try{ return sessionStorage.getItem('user_email') || localStorage.getItem('user_email') || ''; }catch(e){ return ''; }
    }
    function setUserEmail(v){
      try{
        if(v && v.trim()) {
          sessionStorage.setItem('user_email', v.trim());
          localStorage.setItem('user_email', v.trim());
        }
      }catch(e){}
    }
    function refreshIdentityChip(){
      const uid = getUserId();
      const email = getUserEmail();
      const idEl = document.getElementById('chip_user_id');
      const emEl = document.getElementById('chip_user_email');
      if(idEl) idEl.textContent = uid ? String(uid) : '—';
      if(emEl) emEl.textContent = email || '—';
    }

    async function apiFetch(url, options={}){
      const opts = { ...options };
      if(!(opts.headers instanceof Headers)){
        opts.headers = new Headers(opts.headers || {});
      }
      const uid = getUserId();
      if(uid){
        opts.headers.set('x-user-id', String(uid));
      }
      return fetch(url, opts);
    }

    function logout(){ try{ localStorage.clear(); sessionStorage.clear(); }catch(e){} window.location.href = "/ui/"; }

    function showSection(id, ev){
      document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));
      let target = null;
      if (ev) {
        try {
          if (ev.target) target = ev.target.closest ? ev.target.closest('.nav-link') : null;
          else if (ev.classList && ev.classList.contains && ev.classList.contains('nav-link')) target = ev;
        } catch (e) { target = null; }
      }
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
      const ids=['up_month','dec_month','stmt_month','sch_month','ter_month','ap_month','mp_month','af_month','mr_month'];
      ids.forEach(id=>{ const el=document.getElementById(id); if(!el) return; el.innerHTML=''; labels.forEach(l=>{ const opt=document.createElement('option'); opt.value=l; opt.textContent=l; el.appendChild(opt); }); });
    }

    async function loadAgents(){
      const r=await apiFetch('/api/admin/agents?limit=1000'); const j=await r.json(); AGENTS=j.items||[];
      const ids=['user_agent','up_agent','dec_agent','stmt_agent','sch_agent','ter_agent','ap_agent','mp_agent','af_agent','mr_agent','trk_agent','edit_user_agent'];
      ids.forEach(id=>{ const el=document.getElementById(id); if(!el) return; el.innerHTML='<option value="">- select -</option>'; AGENTS.forEach(a=>{ const opt=document.createElement('option'); opt.value=a.agent_code; opt.textContent=`${a.agent_code}${a.agent_name ? ' — '+a.agent_name : ''}`; el.appendChild(opt); }); });
      const tb=document.getElementById('agents_tbody'); if(tb){ tb.innerHTML=''; if(!AGENTS.length) tb.innerHTML='<tr><td colspan="7" class="text-muted text-center">No agents</td></tr>'; AGENTS.forEach(a=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${a.agent_code||''}</td><td>${a.agent_name||''}</td><td>${a.license_number||''}</td><td>${a.is_active? '1':'0'}</td><td>${a.created_at||''}</td><td>${a.updated_at||''}</td><td><button class="btn btn-sm btn-outline-warning me-1" onclick="editAgent('${a.agent_code}')"><i class="bi bi-pencil"></i></button><button class="btn btn-sm btn-outline-danger" onclick="deactivateAgent('${a.agent_code}')"><i class="bi bi-x-circle"></i></button></td>`; tb.appendChild(tr); }); }
    }

    async function upsertAgent(){
      const body={ agent_code: document.getElementById('agent_code').value.trim(), agent_name: document.getElementById('agent_name').value.trim(), license_number: document.getElementById('license_number').value.trim(), is_active: true };
      const r=await apiFetch('/api/admin/agents/upsert',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const j=await r.json(); document.getElementById('agent_result').innerText=JSON.stringify(j); await loadAgents();
    }

    async function editAgent(code){
      const r=await apiFetch(`/api/admin/agents/${encodeURIComponent(code)}`); const j=await r.json();
      if(j.status==='NOT_FOUND'){ alert('Agent not found'); return; }
      const a=j.item;
      document.getElementById('agent_edit_panel').style.display='block';
      document.getElementById('edit_agent_code').value=a.agent_code||'';
      document.getElementById('edit_agent_name').value=a.agent_name||'';
      document.getElementById('edit_agent_license').value=a.license_number||'';
      document.getElementById('edit_agent_active').value=(a.is_active? '1':'0');
      document.getElementById('agent_edit_result').innerText='';
    }
    async function submitEditAgent(){
      const code=document.getElementById('edit_agent_code').value;
      const body={
        agent_name: document.getElementById('edit_agent_name').value,
        license_number: document.getElementById('edit_agent_license').value,
        is_active: document.getElementById('edit_agent_active').value==='1'
      };
      const r=await apiFetch(`/api/admin/agents/${encodeURIComponent(code)}`,{method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const j=await r.json();
      document.getElementById('agent_edit_result').innerText=JSON.stringify(j);
      await loadAgents();
    }
    async function deactivateAgent(code){
      if(!confirm(`Deactivate agent ${code}?`)) return;
      const r=await apiFetch(`/api/admin/agents/deactivate/${encodeURIComponent(code)}`,{method:'POST'}); await r.json();
      await loadAgents();
    }

    async function upsertUser(){
      const body={ email: document.getElementById('user_email').value.trim(), password_hash: document.getElementById('user_phash').value.trim(), agent_code: document.getElementById('user_agent').value || null, role: document.getElementById('user_role').value, is_active: document.getElementById('user_active').value==='true', is_verified: document.getElementById('user_verified').value==='true' };
      setUserEmail(body.email);
      const r=await apiFetch('/api/admin/users/upsert',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const j=await r.json(); document.getElementById('user_result').innerText=JSON.stringify(j); await loadUsers(); refreshIdentityChip();
    }
    async function loadUsers(){
      const r=await apiFetch('/api/admin/users?limit=1000'); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('users_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No users</td></tr>'; rows.forEach(u=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${u.id||''}</td><td>${u.email||''}</td><td>${u.role||''}</td><td>${u.agent_code||''}</td><td>${u.is_active?'true':'false'}</td><td>${u.is_verified?'true':'false'}</td><td>${u.last_login||''}</td><td><button class="btn btn-sm btn-outline-warning me-1" onclick="editUser(${u.id})"><i class="bi bi-pencil"></i></button><button class="btn btn-sm btn-outline-danger" onclick="deleteUser(${u.id})"><i class="bi bi-trash"></i></button></td>`; tb.appendChild(tr); }); }
    async function editUser(id){
      const r=await apiFetch(`/api/admin/users/${id}`); const j=await r.json();
      if(j.status==='NOT_FOUND'){ alert('User not found'); return; }
      const u=j.item;
      document.getElementById('user_edit_panel').style.display='block';
      document.getElementById('edit_user_id').value=u.id;
      document.getElementById('edit_user_email').value=u.email||'';
      document.getElementById('edit_user_phash').value='';
      document.getElementById('edit_user_agent').value=u.agent_code||'';
      document.getElementById('edit_user_role').value=u.role||'agent';
      document.getElementById('edit_user_active').value=(u.is_active? 'true':'false');
      document.getElementById('edit_user_verified').value=(u.is_verified? 'true':'false');
      document.getElementById('user_edit_result').innerText='';
    }
    async function submitEditUser(){
      const id=document.getElementById('edit_user_id').value;
      const body={
        email: document.getElementById('edit_user_email').value.trim(),
        password_hash: document.getElementById('edit_user_phash').value.trim() || null,
        agent_code: document.getElementById('edit_user_agent').value || null,
        role: document.getElementById('edit_user_role').value,
        is_active: document.getElementById('edit_user_active').value==='true',
        is_verified: document.getElementById('edit_user_verified').value==='true'
      };
      if(!body.password_hash) delete body.password_hash;
      setUserEmail(body.email);
      const r=await apiFetch(`/api/admin/users/${id}`,{method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const j=await r.json();
      document.getElementById('user_edit_result').innerText=JSON.stringify(j);
      await loadUsers(); refreshIdentityChip();
    }
    async function deleteUser(id){
      if(!confirm(`Delete user ${id}? This cannot be undone.`)) return;
      const r=await apiFetch(`/api/admin/users/${id}`,{method:'DELETE'}); await r.json();
      await loadUsers();
    }

    async function loadUploads(){
      const params=new URLSearchParams(); const ac=document.getElementById('up_agent').value; const mm=document.getElementById('up_month').value; const dt=document.getElementById('up_doc').value; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt);
      const r=await apiFetch(`/api/admin/uploads?${params.toString()}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('up_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No uploads</td></tr>'; rows.forEach(u=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${u.UploadID}</td><td>${u.agent_code||''}</td><td>${u.doc_type||''}</td><td>${u.FileName||''}</td><td>${u.month_year||''}</td><td>${u.UploadTimestamp||''}</td><td>${u.is_active?'1':'0'}</td><td>${u.is_active? `<button class="btn btn-sm btn-outline-danger" onclick="deactivateUpload(${u.UploadID})"><i class="bi bi-x-circle"></i></button>` : `<button class="btn btn-sm btn-outline-success" onclick="enableUpload(${u.UploadID})"><i class="bi bi-check-circle"></i></button>`}</td>`; tb.appendChild(tr); }); }
    function downloadUploadsCSV(){ const params=new URLSearchParams(); const ac=document.getElementById('up_agent').value; const mm=document.getElementById('up_month').value; const dt=document.getElementById('up_doc').value; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(dt) params.append('doc_type',dt); window.open(`/api/admin/uploads.csv?${params.toString()}`,'_blank'); }
    async function deactivateUpload(id){ const r=await apiFetch(`/api/admin/uploads/${id}`,{method:'DELETE'}); await r.json(); await loadUploads(); }
    async function enableUpload(id){ const r=await apiFetch(`/api/admin/uploads/enable/${id}`,{method:'POST'}); await r.json(); await loadUploads(); }

    async function deactivateOlder(){ const body={ agent_code: document.getElementById('dec_agent').value, month_year: document.getElementById('dec_month').value, doc_type: document.getElementById('dec_doc').value }; const r=await apiFetch('/api/admin/uploads/deactivate-older',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); const j=await r.json(); document.getElementById('dec_result').innerText=JSON.stringify(j); await loadUploads(); }

    async function loadTracker(){ const ac=document.getElementById('trk_agent').value; if(!ac){ document.getElementById('trk_tbody').innerHTML='<tr><td colspan="3" class="text-muted text-center">Choose agent</td></tr>'; return; } const r=await apiFetch(`/api/admin/uploads/tracker?agent_code=${encodeURIComponent(ac)}&months_back=36`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('trk_tbody'); tb.innerHTML=''; if(!rows.length){ tb.innerHTML='<tr><td colspan="3" class="text-muted text-center">No data</td></tr>'; return; } rows.forEach(x=>{ const s=x.statement? `<span class="badge badge-ok">✓</span>`:`<span class="badge badge-no">✗</span>`; const sc=x.schedule? `<span class="badge badge-ok">✓</span>`:`<span class="badge badge-no">✗</span>`; const tr=document.createElement('tr'); tr.innerHTML=`<td>${x.month_year}</td><td>${s}</td><td>${sc}</td>`; tb.appendChild(tr); }); }

    async function loadStatements(){ const params=new URLSearchParams(); const ac=document.getElementById('stmt_agent').value; const mm=document.getElementById('stmt_month').value; const po=document.getElementById('stmt_policy').value.trim(); if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po); const r=await apiFetch(`/api/admin/statements?${params.toString()}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('stmt_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="9" class="text-muted text-center">No data</td></tr>'; rows.forEach(s=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${s.statement_id}</td><td>${s.agent_code||''}</td><td>${s.policy_no||''}</td><td>${s.holder||''}</td><td>${s.policy_type||''}</td><td>${s.pay_date||''}</td><td>${s.premium||''}</td><td>${s.com_amt||''}</td><td>${s.month_year || s.MONTH_YEAR || ''}</td>`; tb.appendChild(tr); }); }
    function downloadStatementsCSV(){ const params=new URLSearchParams(); const ac=document.getElementById('stmt_agent').value; const mm=document.getElementById('stmt_month').value; const po=document.getElementById('stmt_policy').value.trim(); if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po); window.open(`/api/admin/statements.csv?${params.toString()}`,'_blank'); }

    async function loadSchedules(){ const params=new URLSearchParams(); const ac=document.getElementById('sch_agent').value; const mm=document.getElementById('sch_month').value; const lo=document.getElementById('sch_latest').value||'1'; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(ac) params.append('latest_only',lo); const r=await apiFetch(`/api/admin/schedule?${params.toString()}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('sch_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>'; rows.forEach(sc=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${sc.schedule_id}</td><td>${sc.agent_code||''}</td><td>${sc.commission_batch_code||''}</td><td>${sc.total_premiums||''}</td><td>${sc.income||''}</td><td>${sc.total_deductions||''}</td><td>${sc.net_commission||''}</td><td>${sc.month_year||''}</td>`; tb.appendChild(tr); }); }
    function downloadSchedulesCSV(){ const params=new URLSearchParams(); const ac=document.getElementById('sch_agent').value; const mm=document.getElementById('sch_month').value; const lo=document.getElementById('sch_latest').value||'1'; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(ac) params.append('latest_only',lo); window.open(`/api/admin/schedule.csv?${params.toString()}`,'_blank'); }

    async function loadTerminated(){ const params=new URLSearchParams(); const ac=document.getElementById('ter_agent').value; const mm=document.getElementById('ter_month').value; const po=document.getElementById('ter_policy').value.trim(); if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po); const r=await apiFetch(`/api/admin/terminated?${params.toString()}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('ter_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>'; rows.forEach(t=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${t.terminated_id}</td><td>${t.agent_code||''}</td><td>${t.policy_no||''}</td><td>${t.holder||''}</td><td>${t.status||''}</td><td>${t.reason||''}</td><td>${t.month_year||''}</td><td>${t.termination_date||''}</td>`; tb.appendChild(tr); }); }
    function downloadTerminatedCSV(){ const params=new URLSearchParams(); const ac=document.getElementById('ter_agent').value; const mm=document.getElementById('ter_month').value; const po=document.getElementById('ter_policy').value.trim(); if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(po) params.append('policy_no',po); window.open(`/api/admin/terminated.csv?${params.toString()}`,'_blank'); }

    async function loadActivePolicies(){ const params=new URLSearchParams(); const ac=document.getElementById('ap_agent').value; const mm=document.getElementById('ap_month').value; const st=document.getElementById('ap_status').value; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(st) params.append('status',st); const r=await apiFetch(`/api/admin/active-policies?${params.toString()}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('active_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="8" class="text-muted text-center">No data</td></tr>'; rows.forEach(a=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${a.id}</td><td>${a.agent_code||''}</td><td>${a.policy_no||''}</td><td>${a.policy_type||''}</td><td>${a.holder_name||''}</td><td>${a.last_seen_month_year||''}</td><td>${a.last_premium||''}</td><td>${a.status||''}</td>`; tb.appendChild(tr); }); }
    function downloadActivePoliciesCSV(){ const params=new URLSearchParams(); const ac=document.getElementById('ap_agent').value; const mm=document.getElementById('ap_month').value; const st=document.getElementById('ap_status').value; if(ac) params.append('agent_code',ac); if(mm) params.append('month_year',mm); if(st) params.append('status',st); window.open(`/api/admin/active-policies.csv?${params.toString()}`,'_blank'); }

    async function loadMissing(){ const ac=document.getElementById('mp_agent').value; const mm=document.getElementById('mp_month').value; if(!ac||!mm) return; const r=await apiFetch(`/api/admin/missing?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(mm)}`); const j=await r.json(); const rows=j.items||[]; const tb=document.getElementById('missing_tbody'); tb.innerHTML=''; if(!rows.length) tb.innerHTML='<tr><td colspan="3" class="text-muted text-center">No missing policies</td></tr>'; rows.forEach(m=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${m.policy_no||''}</td><td>${m.last_seen_month||''}</td><td>${m.last_premium||''}</td>`; tb.appendChild(tr); }); }
    function downloadMissingCSV(){ const ac=document.getElementById('mp_agent').value; const mm=document.getElementById('mp_month').value; if(!ac||!mm) return; window.open(`/api/admin/missing.csv?agent_code=${encodeURIComponent(ac)}&month_year=${encodeURIComponent(mm)}`,'_blank'); }

    async function generateMonthlyAgentMonth(){
      const ac=document.getElementById('mr_agent').value;
      const mm=document.getElementById('mr_month').value;
      const an=document.getElementById('mr_agent_name').value.trim();
      const uid=document.getElementById('mr_user_id').value.trim();
      const upid=document.getElementById('mr_upload_id').value.trim();
      const out=document.getElementById('mr_out').value.trim();
      const fd=new FormData();
      fd.append('agent_code',ac);
      fd.append('month_year',mm);
      if(an) fd.append('agent_name',an);
      if(uid) fd.append('user_id',uid);
      if(upid) fd.append('upload_id',upid);
      fd.append('out',out);

      if(uid) setUserId(uid);
      refreshIdentityChip();

      const r=await apiFetch('/api/admin/reports/generate-agent-month',{method:'POST', body:fd});
      const j=await r.json();
      const el=document.getElementById('mr_result');
      el.innerHTML=`<div class="alert alert-success"><div><strong>Status:</strong> ${j.status||'UNKNOWN'}</div><div><strong>Agent:</strong> ${j.agent_code||ac} &nbsp; (${j.agent_name||an||ac})</div><div><strong>Month:</strong> ${j.month_year||mm}</div><div><strong>Report period:</strong> ${j.report_period||''}</div><div><strong>Upload used:</strong> ${j.upload_id_used ?? j.upload_id ?? ''}</div><div><strong>Expected rows inserted:</strong> ${j.expected_rows_inserted ?? 0}</div><div><strong>PDF:</strong> ${(j.pdf && j.pdf.pdf_path) ? j.pdf.pdf_path : 'generated'}</div></div><pre class="code">${JSON.stringify(j,null,2)}</pre>`;
    }

    (async function init(){
      await loadAgents();
      populateMonthSelects();
      refreshIdentityChip();
    })();
  </script>
</body>
</html>
    """.strip()
    return HTMLResponse(html)
