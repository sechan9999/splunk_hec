from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session
from app.experience.workspace import assemble_workspace, save_layout
from app.security.auth import Identity, current_identity

router = APIRouter(prefix="/workspace", tags=["experience"])

_DASHBOARD_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unified Ops AX — Workspace</title>
<style>
 :root{color-scheme:light dark}
 body{font-family:system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:14px 20px;background:#171a21;border-bottom:1px solid #262b36;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
 input{background:#0f1115;border:1px solid #333;color:#e6e6e6;padding:8px;border-radius:6px;flex:1;min-width:200px}
 button{background:#3b82f6;border:0;color:#fff;padding:8px 14px;border-radius:6px;cursor:pointer}
 main{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
 .card{background:#171a21;border:1px solid #262b36;border-radius:10px;overflow:hidden}
 .card h3{margin:0;padding:12px 14px;background:#1e222b;font-size:14px;border-bottom:1px solid #262b36}
 pre{margin:0;padding:12px 14px;font-size:12px;overflow:auto;max-height:280px;white-space:pre-wrap}
 .who{opacity:.7;font-size:13px}
</style></head><body>
<header>
 <strong>Unified Ops AX</strong>
 <input id="tok" placeholder="Bearer token (POST /hub/employees/{id}/token)">
 <button onclick="load()">Load workspace</button>
 <span class="who" id="who"></span>
</header>
<main id="grid"></main>
<script>
async function load(){
 const t=document.getElementById('tok').value.trim();
 const r=await fetch('/workspace/me',{headers:{Authorization:'Bearer '+t}});
 const g=document.getElementById('grid'); g.innerHTML='';
 if(!r.ok){document.getElementById('who').textContent='auth failed ('+r.status+')';return;}
 const d=await r.json();
 document.getElementById('who').textContent=d.employee.name+' · '+d.employee.role;
 for(const w of d.widgets){
  const c=document.createElement('div');c.className='card';
  c.innerHTML='<h3>'+w.label+'</h3><pre>'+JSON.stringify(w.data,null,2)+'</pre>';
  g.appendChild(c);
 }
}
</script></body></html>"""


class LayoutIn(BaseModel):
    widgets: list[str]


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Self-contained thin client for the experience layer. Enter an employee
    token to render that role's assembled workspace."""
    return _DASHBOARD_HTML


@router.get("/me")
def my_workspace(
    identity: Identity = Depends(current_identity),
    session: Session = Depends(get_session),
):
    return assemble_workspace(session, identity)


@router.put("/me/layout")
def update_layout(
    body: LayoutIn,
    identity: Identity = Depends(current_identity),
    session: Session = Depends(get_session),
):
    saved = save_layout(session, identity, body.widgets)
    return {"layout": saved}
