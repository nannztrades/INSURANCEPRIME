
# src/api/ui_pages.py
from __future__ import annotations
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import importlib, importlib.util

router = APIRouter(prefix="/ui", tags=["UI"])

def _opt_attr(module: str, attr: str):
    spec = importlib.util.find_spec(module)
    if not spec:
        return None
    try:
        mod = importlib.import_module(module)
        return getattr(mod, attr, None)
    except Exception:
        return None

# Auth + DB helpers (optional enrichment)
decode_token      = _opt_attr("src.services.auth_service", "decode_token")
TOKEN_COOKIE_NAME = _opt_attr("src.services.auth_service", "TOKEN_COOKIE_NAME") or "access_token"
get_conn          = _opt_attr("src.ingestion.db", "get_conn")

def _get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Enrich identity from cookie token and DB (if available)."""
    if not decode_token:
        return None
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        return None
    try:
        payload = decode_token(token) or {}
        uid = payload.get("user_id")
        if not uid or not get_conn:
            return payload
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, agent_code, agent_name, role FROM `users` WHERE `id`=%s",
                    (uid,)
                )
                row = cur.fetchone() or None
                if row:
                    payload.update(row)
        finally:
            conn.close()
        return payload
    except Exception:
        return None

@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    user = _get_current_user(request)

    logged_in_html = ""
    if user:
        role = str(user.get("role") or "").lower()
        email = user.get("email", user.get("user_email", ""))
        agent_code = user.get("agent_code", "")
        agent_name = user.get("agent_name") or (email or "Agent")

        if role in ("admin", "superuser"):
            logged_in_html = (
                f"""
            <div class="alert alert-success mb-4">
              Logged in as <strong>{email}</strong> ({role})
              <div class="mt-2 d-flex gap-2">
                <a href="/ui/admin" class="btn btn-success btn-sm">Admin Dashboard</a>
                <a href="/ui/agent" class="btn btn-outline-success btn-sm">Agent Selector</a>
                <a href="/api/auth/logout" class="btn btn-outline-danger btn-sm">Logout</a>
              </div>
            </div>
                """.strip()
            )
        else:
            target = f"/ui/agent/{agent_code}" if agent_code else "/ui/agent"
            logged_in_html = (
                f"""
            <div class="alert alert-success mb-4">
              Logged in as <strong>{agent_name}</strong>
              <div class="mt-2 d-flex gap-2">
                <a href="{target}" class="btn btn-success btn-sm">My Dashboard</a>
                <a href="/api/auth/logout" class="btn btn-outline-danger btn-sm">Logout</a>
              </div>
            </div>
                """.strip()
            )

    # NOTE: All CSS/JS braces are doubled {{ }} to avoid f-string parsing.
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1.0" />
  <title>ICRS - Insurance Commission Reconciliation</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" />
  <style>
    :root {{ --primary:#059669; --dark1:#1e1b4b; --dark2:#4f46e5; }}
    body {{
      background: linear-gradient(135deg, var(--dark1), var(--dark2));
      min-height: 100vh; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
    }}
    .hero {{ padding: 80px 0; color: white; text-align: center; }}
    .hero h1 {{ font-weight: 800; letter-spacing:.5px; font-size: 2.4rem; }}
    .card-wrap {{ display:flex; justify-content:center; gap:28px; flex-wrap:wrap; margin-top:28px; }}
    .card-lg {{
      width: 380px; background:white; border-radius: 20px; padding: 36px;
      box-shadow: 0 18px 60px rgba(0,0,0,.35); text-align:center;
    }}
    .card-compact {{
      width: 260px; background:white; border-radius: 16px; padding: 22px;
      box-shadow: 0 12px 40px rgba(0,0,0,.28); text-align:center; opacity:.92;
    }}
    .icon-pill {{
      width:74px; height:74px; border-radius:50%; display:flex; align-items:center;
      justify-content:center; margin: 0 auto 14px; font-size:32px; color:white;
    }}
    .icon-agent {{ background: linear-gradient(135deg, #22c55e, #059669); }}
    .icon-admin {{ background: linear-gradient(135deg, #1e1b4b, #4f46e5); }}
    .icon-super {{ background: linear-gradient(135deg, #0ea5e9, #2563eb); }}
    .btn-primary-soft {{
      background: linear-gradient(135deg, #22c55e, #059669); color: white; border: none;
    }}
    .btn-dark-soft {{ background: linear-gradient(135deg, #1e1b4b, #4f46e5); color: white; border:none; }}
    .btn-blue-soft {{ background: linear-gradient(135deg, #0ea5e9, #2563eb); color: white; border:none; }}
    .identity {{
      position: fixed; left: 16px; bottom: 16px; background: rgba(255,255,255,.12);
      border:1px solid rgba(255,255,255,.25); color:#fff; border-radius: 12px;
      backdrop-filter: blur(6px); padding: 10px 14px; font-size:.9rem;
    }}
    .identity small {{ opacity:.85; }}
    .w-100 {{ width:100%; }}
  </style>
</head>
<body>
  <section class="hero">
    <div class="container">
      {logged_in_html}
      <h1><i class="bi bi-shield-check"></i> ICRS</h1>
      <p class="lead">Insurance Commission Reconciliation System</p>

      <div class="card-wrap">
        <!-- AGENT -->
        <div class="card-lg">
          <div class="icon-pill icon-agent"><i class="bi bi-person-badge"></i></div>
          <h4>Agent Portal</h4>
          <a href="/ui/login?role=agent" class="btn btn-primary-soft w-100">
            <i class="bi bi-box-arrow-in-right me-2"></i> Agent Login
          </a>
          <div class="mt-3">
            <a href="/ui/agent" class="btn btn-outline-success btn-sm">
              <i class="bi bi-people"></i> Browse Agent Dashboards (admin-only)
            </a>
          </div>
        </div>

        <!-- ADMIN -->
        <div class="card-compact">
          <div class="icon-pill icon-admin"><i class="bi bi-shield-lock"></i></div>
          <h5 class="mb-2">Admin</h5>
          <a href="/ui/login?role=admin" class="btn btn-dark-soft w-100">
            <i class="bi bi-box-arrow-in-right me-1"></i> Admin Login
          </a>
          <div class="mt-2">
            <a href="/ui/admin" class="btn btn-outline-secondary btn-sm">
              Open Admin Dashboard
            </a>
          </div>
        </div>

        <!-- SUPERUSER -->
        <div class="card-compact">
          <div class="icon-pill icon-super"><i class="bi bi-person-gear"></i></div>
          <h5 class="mb-2">Superuser</h5>
          <a href="/ui/login?role=superuser" class="btn btn-blue-soft w-100">
            <i class="bi bi-box-arrow-in-right me-1"></i> Superuser Login
          </a>
        </div>
      </div>

      <p class="small text-light mt-4">
        Email <a class="text-white" href="mailto:nannztrades@gmail.com">nannztrades@gmail.com</a> for enquiries or help.
      </p>
    </div>
  </section>

  <div class="identity" id="identityChip" style="display:none;">
    <div><i class="bi bi-person-circle me-1"></i> <strong id="idLabel">User</strong></div>
    <small id="emailLabel"></small>
  </div>

<script>
  // Cookie-based identity (works in local dev with AUTH_COOKIE_SECURE=0, SameSite=lax)
  async function refreshIdentityChip() {{
    try {{
      const r = await fetch('/api/auth/me', {{ method: 'GET', credentials: 'same-origin' }});
      const j = await r.json();
      if (!j || j.status !== 'OK' || !j.identity) return;
      const id = j.identity.user_id || null;
      const email = j.identity.user_email || j.identity.email || '';
      document.getElementById('identityChip').style.display = 'block';
      document.getElementById('idLabel').textContent = id ? ('ID ' + id) : 'User';
      document.getElementById('emailLabel').textContent = email ? ('Email: ' + email) : '';
    }} catch (e) {{
      // Optional fallback to storage if needed
      const sid = parseInt(sessionStorage.getItem('user_id') || localStorage.getItem('user_id'));
      const semail = sessionStorage.getItem('user_email') || localStorage.getItem('user_email') || '';
      if (!sid && !semail) return;
      document.getElementById('identityChip').style.display = 'block';
      document.getElementById('idLabel').textContent = sid ? ('ID ' + sid) : 'User';
      document.getElementById('emailLabel').textContent = semail ? ('Email: ' + semail) : '';
    }}
  }}
  refreshIdentityChip();
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)

@router.get("/login", response_class=HTMLResponse)
def login(request: Request):
    role = str(request.query_params.get("role") or "").lower()
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Login · ICRS</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" />
</head>
<body class="bg-light">
  <div class="container py-5">
    <h2 class="mb-4"><i class="bi bi-box-arrow-in-right"></i> Login</h2>

    <ul class="nav nav-tabs">
      <li class="nav-item"><a id="tab-agent" class="nav-link {'active' if role=='agent' else ''}" href="#agent" onclick="show('agent', this)">Agent</a></li>
      <li class="nav-item"><a id="tab-admin" class="nav-link {'active' if role in ('admin','superuser') else ''}" href="#admin" onclick="show('admin', this)">Admin / Superuser</a></li>
    </ul>

    <div id="agent" class="p-3 border border-top-0 {'d-block' if role=='agent' else 'd-none'}">
      <form onsubmit="return agentLogin(this)">
        <div class="mb-3">
          <label class="form-label">Agent Code</label>
          <input name="agent_code" class="form-control" required />
        </div>
        <button class="btn btn-success w-100">Login as Agent</button>
      </form>
    </div>

    <div id="admin" class="p-3 border border-top-0 {'d-block' if role in ('admin','superuser') else 'd-none'}">
      <form onsubmit="return adminLogin(this)">
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label">User ID (optional)</label>
            <input name="user_id" class="form-control" type="number" />
          </div>
          <div class="col-md-6">
            <label class="form-label">Email (optional)</label>
            <input name="email" class="form-control" type="email" />
          </div>
        </div>
        <div class="mt-3">
          <label class="form-label">Password</label>
          <input name="password" class="form-control" type="password" required />
        </div>
        <small class="text-muted">Provide either <strong>User ID</strong> or <strong>Email</strong>, plus password.</small>
        <button class="btn btn-primary w-100 mt-3">Login as Admin/Superuser</button>
      </form>
    </div>

    <div id="msg" class="alert alert-info mt-3 d-none"></div>
  </div>

<script>
  function show(id, el) {{
    document.getElementById('agent').className = 'p-3 border border-top-0 ' + (id==='agent'?'d-block':'d-none');
    document.getElementById('admin').className = 'p-3 border border-top-0 ' + (id==='admin'?'d-block':'d-none');
    document.querySelectorAll('.nav-link').forEach(a=>a.classList.remove('active'));
    if(el && el.classList) el.classList.add('active');
  }}

  function setMsg(text, kind='info') {{
    const m=document.getElementById('msg');
    m.className='alert alert-'+kind+' mt-3';
    m.textContent=text;
    m.classList.remove('d-none');
  }}

  function toFormBody(obj) {{
    const p=new URLSearchParams();
    Object.entries(obj).forEach(([k,v])=>{{ if(v!==undefined && v!==null) p.append(k, String(v)); }});
    return p;
  }}

  async function agentLogin(form) {{
    const body = toFormBody({{ agent_code: form.agent_code.value.trim() }});
    const r = await fetch('/api/auth/login/agent', {{ method:'POST', headers: {{'Content-Type':'application/x-www-form-urlencoded'}}, body }});
    const j = await r.json();
    if(!r.ok){{ setMsg(j.detail||'Login failed', 'danger'); return false; }}
    window.location.href = '/ui/';
    return false;
  }}

  async function adminLogin(form) {{
    const body = toFormBody({{
      user_id: form.user_id.value||'',
      email: form.email.value||'',
      password: form.password.value
    }});
    const r = await fetch('/api/auth/login/user', {{ method:'POST', headers: {{'Content-Type':'application/x-www-form-urlencoded'}}, body }});
    const j = await r.json();
    if(!r.ok){{ setMsg(j.detail||'Login failed', 'danger'); return false; }}
    window.location.href = '/ui/';
    return false;
  }}
</script>
</body>
</html>
    """
    return HTMLResponse(content=html)

@router.get("/agent/upload")
def agent_upload_page_redirect():
    return RedirectResponse(url="/ui/")
