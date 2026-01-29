
# src/api/ui_pages.py
from __future__ import annotations
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["UI Pages"])

def _base_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ICRS · UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"/>
  <style>
  body {{ background:#f9fafb; }}
  a.text-link {{ text-decoration:none }}
  </style>
</head>
<body>
{body}
</body>
</html>"""

# ---------- Landing ----------
@router.get("/", response_class=HTMLResponse)
async def landing_page() -> HTMLResponse:
    # Full-page landing with quick links to the dashboards
    return HTMLResponse(r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ICRS · Welcome</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
  <style>
  body{
    margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:
      radial-gradient(circle at 10% 10%, #22d3ee33 0, transparent 45%),
      radial-gradient(circle at 90% 90%, #a855f733 0, transparent 45%),
      #0b1020;
    color:#e5e7eb;font-family:system-ui,-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif;
  }
  .wrap{max-width:980px;width:100%;padding:24px;position:relative}
  .top-left{
    position:absolute;left:24px;top:24px;display:flex;gap:.5rem;flex-wrap:wrap;
  }
  .btn-top{
    --bs-btn-padding-y:.25rem; --bs-btn-padding-x:.6rem; --bs-btn-font-size:.72rem;
    border-radius:999px; background:rgba(255,255,255,.08); color:#e5e7eb; border:1px solid rgba(255,255,255,.2)
  }
  .btn-top:hover{ background:rgba(255,255,255,.15); color:#fff }
  .brand{display:flex;gap:12px;align-items:center;justify-content:center;margin-bottom:18px}
  .brand .logo{font-size:20px}
  .brand h1{font-size:20px;letter-spacing:.18em;text-transform:uppercase;margin:0}
  .cardy{
    background:#0f172a;border:1px solid #1f2937;border-radius:16px;padding:28px 22px;
    box-shadow:0 24px 70px rgba(0,0,0,.6);
  }
  .btn-grad{background:linear-gradient(90deg,#22d3ee,#a855f7);border:none;border-radius:999px}
  .agent-title{
    display:flex;align-items:center;gap:.6rem;font-weight:800;font-size:1.35rem;letter-spacing:.02em;justify-content:center;
  }
  .footer{ margin-top:24px;text-align:center;color:#9ca3af;font-size:.9rem }
  </style>
</head>
<body>
  <div class="wrap">
    <!-- Small Admin / Superuser buttons -->
    <div class="top-left">
      <a class="btn btn-top" href="/ui/login/admin" title="Admin Login" aria-label="Admin Login">🛡️</a>
      <a class="btn btn-top" href="/ui/login/superuser" title="Superuser Login" aria-label="Superuser Login">⚖️</a>
    </div>

    <!-- Centered Agent card -->
    <div class="brand">
      <div class="logo">🔐</div>
      <h1>ICRS</h1>
    </div>

    <div class="row justify-content-center">
      <div class="col-md-6 col-lg-5">
        <div class="cardy text-center">
          <div class="agent-title mb-3"><span>Agent</span></div>
          <a class="btn btn-grad w-100" href="/ui/agent/"><span class="me-1">➡</span>Open Agent Dashboard</a>
        </div>
      </div>
    </div>

    <div class="footer">
      contact <a class="text-link" href="mailto:nannztrades@gmail.com">nannztrades@gmail.com</a> for any info or assistance
    </div>
  </div>
</body>
</html>""")

# ---------- Shared JS helpers ----------
_HELPERS = r"""
<script>
function setMsg(id, txt, kind){
  const el = document.getElementById(id);
  if(!el) return;
  el.textContent = txt ?? '';
  el.className = 'small';
  if(kind === 'error'){ el.classList.add('text-danger'); }
  else if(kind === 'success'){ el.classList.add('text-success'); }
  else { el.classList.add('text-muted'); }
}
function toBody(obj){
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k,v]) => p.append(k, v));
  return p.toString();
}
async function getCsrf(){
  const r = await fetch('/api/auth/csrf', {credentials:'same-origin'});
  if(!r.ok){ throw new Error('Failed to get CSRF token'); }
  const j = await r.json();
  return j.csrf_token;
}
</script>
"""

# ---------- Agent Login (agent_code + password) ----------
@router.get("/login/agent", response_class=HTMLResponse)
async def login_agent_page() -> HTMLResponse:
    body = r"""
<div class="container py-4">
  <div class="d-flex align-items-center justify-content-between mb-2">
    <h3 class="mb-0">Agent Login</h3>
    <a class="btn btn-sm btn-outline-secondary" href="/ui/">← Back</a>
  </div>
  <form onsubmit="return agentLogin(event, this);">
    <div class="mb-3">
      <label class="form-label">Agent Code</label>
      <input name="agent_code" class="form-control" autocomplete="username" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Password</label>
      <input name="code_password" type="password" class="form-control" autocomplete="current-password" required>
    </div>
    <div id="agentMsg" class="small text-muted mb-2"></div>
    <button type="submit" class="btn btn-primary">Login</button>
  </form>
</div>

<script>
async function agentLogin(e, form){
  e.preventDefault();
  const code = (form.agent_code.value ?? '').trim();
  const pass = (form.code_password.value ?? '');
  if(!code || !pass){
    setMsg('agentMsg','Agent Code and Password are required','error');
    return false;
  }
  try{
    const csrf = await getCsrf();
    const r = await fetch('/api/auth/login/agent', {
      method:'POST',
      headers:{ 'Content-Type':'application/x-www-form-urlencoded', 'X-CSRF-Token': csrf },
      body: toBody({agent_code: code, password: pass}),
      credentials:'same-origin'
    });
    if(!r.ok){
      const j = await r.json().catch(()=> ({}));
      setMsg('agentMsg', (j.detail ?? 'Login failed'), 'error');
      return false;
    }
    setMsg('agentMsg','Login OK, redirecting...','success');
    window.location.href = '/ui/agent/';
  }catch(err){
    setMsg('agentMsg', (String(err) || 'Login error'),'error');
  }
  return false;
}
</script>
""" + _HELPERS
    return HTMLResponse(_base_html(body))

# ---------- Admin Login (user_id + password) ----------
def _admin_login_body() -> str:
    return r"""
<div class="container py-4">
  <div class="d-flex align-items-center justify-content-between mb-2">
    <h3 class="mb-0">Admin Login</h3>
    <a class="btn btn-sm btn-outline-secondary" href="/ui/">← Back</a>
  </div>
  <form onsubmit="return adminLogin(event, this);">
    <div class="mb-3">
      <label class="form-label">User ID</label>
      <input name="user_id" type="number" class="form-control" autocomplete="username" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Password</label>
      <input name="password" type="password" class="form-control" autocomplete="current-password" required>
    </div>
    <div id="adminMsg" class="small text-muted mb-2"></div>
    <button type="submit" class="btn btn-primary">Login</button>
  </form>
</div>

<script>
async function adminLogin(e, form){
  e.preventDefault();
  const uid = (form.user_id.value ?? '').trim();
  const pass = (form.password.value ?? '');
  if(!uid || !pass){
    setMsg('adminMsg','User ID and Password are required','error');
    return false;
  }
  try{
    const csrf = await getCsrf();
    const r = await fetch('/api/auth/login/user', {
      method:'POST',
      headers:{ 'Content-Type':'application/x-www-form-urlencoded', 'X-CSRF-Token': csrf },
      body: toBody({user_id: uid, password: pass}),
      credentials:'same-origin'
    });
    if(!r.ok){
      const j = await r.json().catch(()=> ({}));
      setMsg('adminMsg', (j.detail ?? 'Login failed'), 'error');
      return false;
    }
    setMsg('adminMsg','Login OK, checking role...','success');
    const meResp = await fetch('/api/auth/me', { credentials:'same-origin' });
    if(!meResp.ok){
      setMsg('adminMsg', 'Could not verify session after login','error');
      return false;
    }
    const me = await meResp.json();
    const role = String(me?.identity?.role ?? '').toLowerCase();
    if (role === 'admin') window.location.href = '/ui/admin/';
    else if (role === 'superuser') window.location.href = '/ui/superuser/';
    else if (role === 'agent') window.location.href = '/ui/agent/';
    else window.location.href = '/ui/';
  }catch(err){
    setMsg('adminMsg', (String(err) || 'Login error'),'error');
  }
  return false;
}
</script>
""" + _HELPERS

# ---------- Superuser Login (user_id + password) ----------
def _superuser_login_body() -> str:
    return r"""
<div class="container py-4">
  <div class="d-flex align-items-center justify-content-between mb-2">
    <h3 class="mb-0">Superuser Login</h3>
    <a class="btn btn-sm btn-outline-secondary" href="/ui/">← Back</a>
  </div>
  <form onsubmit="return suLogin(event, this);">
    <div class="mb-3">
      <label class="form-label">User ID</label>
      <input name="user_id" type="number" class="form-control" autocomplete="username" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Password</label>
      <input name="password" type="password" class="form-control" autocomplete="current-password" required>
    </div>
    <div id="suMsg" class="small text-muted mb-2"></div>
    <button type="submit" class="btn btn-primary">Login</button>
  </form>
</div>

<script>
async function suLogin(e, form){
  e.preventDefault();
  const uid = (form.user_id.value ?? '').trim();
  const pass = (form.password.value ?? '');
  if(!uid || !pass){
    setMsg('suMsg','User ID and Password are required','error');
    return false;
  }
  try{
    const csrf = await getCsrf();
    const r = await fetch('/api/auth/login/user', {
      method:'POST',
      headers:{ 'Content-Type':'application/x-www-form-urlencoded', 'X-CSRF-Token': csrf },
      body: toBody({user_id: uid, password: pass}),
      credentials:'same-origin'
    });
    if(!r.ok){
      const j = await r.json().catch(()=> ({}));
      setMsg('suMsg', (j.detail ?? 'Login failed'), 'error');
      return false;
    }
    setMsg('suMsg','Login OK, checking role...','success');
    const meResp = await fetch('/api/auth/me', { credentials:'same-origin' });
    if(!meResp.ok){
      setMsg('suMsg', 'Could not verify session after login','error');
      return false;
    }
    const me = await meResp.json();
    const role = String(me?.identity?.role ?? '').toLowerCase();
    if (role === 'superuser') window.location.href = '/ui/superuser/';
    else if (role === 'admin') window.location.href = '/ui/admin/';
    else if (role === 'agent') window.location.href = '/ui/agent/';
    else window.location.href = '/ui/';
  }catch(err){
    setMsg('suMsg', (String(err) || 'Login error'),'error');
  }
  return false;
}
</script>
""" + _HELPERS

@router.get("/login/admin", response_class=HTMLResponse)
async def login_admin_page() -> HTMLResponse:
    return HTMLResponse(_base_html(_admin_login_body()))

@router.get("/login/superuser", response_class=HTMLResponse)
async def login_superuser_page() -> HTMLResponse:
    return HTMLResponse(_base_html(_superuser_login_body()))
