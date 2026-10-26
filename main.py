import csv
import io
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import LoginInput, authenticate, auth_enabled, require_admin
from cache import get_json, invalidate, set_json
from database import Base, engine, get_db
from duplicate_checker import calculate_similarity, classify_similarity, create_hash
from models import Record
from validator import RecordInput

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Data Redundancy Removal System",
    description="Data quality platform with duplicate detection, optional JWT admin access, analytics, and bulk operations.",
    version="3.0.0",
)


@app.get("/", response_class=HTMLResponse)
def home():
    from pathlib import Path
    index = Path(__file__).parent / "static" / "index.html"
    if index.exists():
        html = index.read_text(encoding="utf-8")
        # Inject a lightweight login overlay without requiring a separate frontend build.
        login_script = r"""
<script>
(async function(){
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let enabled = false;
  try { enabled = (await (await fetch('/auth/status')).json()).enabled; } catch (_) {}
  if (!enabled) return;
  const style = document.createElement('style');
  style.textContent = '#authGate{position:fixed;inset:0;z-index:9999;background:#0f172acc;display:grid;place-items:center;padding:20px}#authGate .authbox{background:white;border-radius:18px;padding:28px;width:min(420px,100%);box-shadow:0 20px 80px #0005}#authGate input{margin:6px 0 14px}#authError{color:#b91c1c;font-size:13px;min-height:20px}';
  document.head.appendChild(style);
  const gate=document.createElement('div');gate.id='authGate';
  gate.innerHTML='<div class="authbox"><h2>DataGuard Admin Login</h2><p class="muted">Authentication is enabled for this deployment.</p><form id="authForm"><label for="authUser">Username</label><input id="authUser" autocomplete="username" required><label for="authPass">Password</label><input id="authPass" type="password" autocomplete="current-password" required><div id="authError"></div><button class="btn" type="submit" style="width:100%">Sign in</button></form></div>';
  document.body.appendChild(gate);
  const nativeFetch=window.fetch.bind(window);
  window.fetch=(input,options={})=>{
    const token=localStorage.getItem('dataguard_access_token');
    const headers=new Headers(options.headers||{});
    if(token && !String(input).includes('/auth/token')) headers.set('Authorization','Bearer '+token);
    return nativeFetch(input,{...options,headers});
  };
  document.getElementById('authForm').addEventListener('submit',async e=>{
    e.preventDefault();const err=document.getElementById('authError');err.textContent='';
    try {
      const response=await nativeFetch('/auth/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('authUser').value,password:document.getElementById('authPass').value})});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'Login failed');
      localStorage.setItem('dataguard_access_token',data.access_token);gate.remove();
      if(typeof refreshAll==='function') await refreshAll();
    } catch(ex){err.textContent=esc(ex.message);}
  });
  const oldNotice=window.notice;
  window.addEventListener('storage',e=>{if(e.key==='dataguard_access_token'&&!e.newValue)location.reload()});
})();
</script>
"""
        return html.replace("</body>", login_script + "</body>")
    return "<h1>Data Redundancy Removal System</h1><p>API docs: <a href='/docs'>/docs</a></p>"


@app.get("/health")
def health():
    return {"status": "ok", "service": "data-redundancy-removal-system"}


@app.get("/auth/status")
def auth_status():
    return {"enabled": auth_enabled(), "token_endpoint": "/auth/token"}


@app.post("/auth/token")
def issue_token(login: LoginInput):
    return {"access_token": authenticate(login), "token_type": "bearer", "expires_in": 3600}


@app.get("/auth/me")
def auth_me(user=Depends(require_admin)):
    if not auth_enabled():
        return {"authenticated": False, "auth_enabled": False, "role": "local"}
    return {"authenticated": True, "auth_enabled": True, "username": user["sub"], "role": user["role"]}


def _normalized(record: RecordInput):
    name = " ".join(record.name.split())
    email = str(record.email).lower().strip()
    phone = record.phone.strip()
    normalized = RecordInput(name=name, email=email, phone=phone)
    return normalized, create_hash(name, email, phone)


def _find_match(db: Session, normalized: RecordInput):
    best_match = None
    best_score = 0.0
    # Records are bounded by pagination for reads; this comparison currently scans stored rows.
    for existing in db.query(Record).all():
        score = calculate_similarity(normalized, existing)
        if score > best_score:
            best_score, best_match = score, existing
    return best_match, best_score


@app.post("/records")
def add_record(record: RecordInput, db: Session = Depends(get_db), _user=Depends(require_admin)):
    normalized, record_hash = _normalized(record)
    existing_record = db.query(Record).filter(Record.record_hash == record_hash).first()
    if existing_record:
        return {
            "status": "duplicate",
            "classification": "duplicate",
            "message": "Exact duplicate detected. Data was not added.",
            "existing_record_id": existing_record.id,
            "similarity_score": 100.0,
        }

    best_match, best_score = _find_match(db, normalized)
    classification = classify_similarity(best_score)
    if best_match and classification == "duplicate":
        return {"status": "duplicate", "classification": "duplicate", "similarity_score": best_score,
                "message": "Very similar record detected. Data was not added.", "existing_record_id": best_match.id}
    if best_match and classification == "possible_duplicate":
        return {"status": "review", "classification": "possible_duplicate", "similarity_score": best_score,
                "message": "Possible duplicate detected. Review the matching record before adding.",
                "existing_record_id": best_match.id}

    new_record = Record(name=normalized.name, email=normalized.email, phone=normalized.phone, record_hash=record_hash)
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    invalidate("stats:v1")
    return {"status": "success", "classification": "unique", "message": "Unique record added successfully.",
            "record_id": new_record.id}


@app.get("/records")
def get_records(
    q: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(require_admin),
):
    query = db.query(Record)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Record.name.ilike(term), Record.email.ilike(term), Record.phone.ilike(term)))
    total = query.count()
    records_query = query.order_by(Record.id.desc())
    if page is None and q is None:
        return [{"id": r.id, "name": r.name, "email": r.email, "phone": r.phone} for r in records_query.all()]
    current_page = page or 1
    records = records_query.offset((current_page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{"id": r.id, "name": r.name, "email": r.email, "phone": r.phone} for r in records],
        "total": total,
        "page": current_page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


def _stats(db: Session):
    total = db.query(func.count(Record.id)).scalar() or 0
    domains = db.query(
        func.lower(func.substr(Record.email, func.instr(Record.email, "@") + 1)).label("domain"),
        func.count(Record.id).label("count"),
    ).group_by("domain").order_by(func.count(Record.id).desc()).limit(5).all()
    recent = db.query(Record).order_by(Record.id.desc()).limit(5).all()
    return {
        "total_records": total,
        "unique_records": total,
        "top_email_domains": [{"domain": domain, "count": count} for domain, count in domains],
        "recent_records": [{"id": r.id, "name": r.name, "email": r.email, "phone": r.phone} for r in recent],
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db), _user=Depends(require_admin)):
    cached = get_json("stats:v1")
    if cached is not None:
        return cached
    result = _stats(db)
    set_json("stats:v1", result, ttl=30)
    return result


@app.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), _user=Depends(require_admin)):
    stats = _stats(db)
    phone_lengths = db.query(func.length(Record.phone), func.count(Record.id)).group_by(func.length(Record.phone)).all()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": stats["total_records"],
        "distinct_email_domains": db.query(
            func.count(func.distinct(func.lower(func.substr(Record.email, func.instr(Record.email, "@") + 1)))
        ).scalar() or 0,
        "top_email_domains": stats["top_email_domains"],
        "phone_length_distribution": [{"digits_or_chars": length, "count": count} for length, count in phone_lengths],
        "recent_records": stats["recent_records"],
        "cache": "redis-enabled" if get_json("stats:v1") is not None else "database-fallback-or-cache-miss",
    }


@app.get("/records/export.csv")
def export_records(db: Session = Depends(get_db), _user=Depends(require_admin)):
    records = db.query(Record).order_by(Record.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "phone"])
    for record in records:
        safe_values = []
        for value in [record.id, record.name, record.email, record.phone]:
            text = str(value or "")
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text
            safe_values.append(text)
        writer.writerow(safe_values)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="records-export.csv"'})


@app.delete("/records/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db), _user=Depends(require_admin)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    invalidate("stats:v1")
    return None


@app.post("/records/bulk")
def bulk_add_records(records: list[RecordInput], db: Session = Depends(get_db), _user=Depends(require_admin)):
    if not records:
        raise HTTPException(status_code=422, detail="At least one record is required")
    if len(records) > 500:
        raise HTTPException(status_code=413, detail="Maximum 500 records per import")
    result = {"added": 0, "duplicates": 0, "review": 0, "errors": []}
    existing_rows = db.query(Record).all()
    for index, record in enumerate(records, start=1):
        normalized, record_hash = _normalized(record)
        if any(existing.record_hash == record_hash for existing in existing_rows):
            result["duplicates"] += 1
            continue
        match, score = _find_match(db, normalized)
        classification = classify_similarity(score)
        if match and classification == "duplicate":
            result["duplicates"] += 1
            continue
        if match and classification == "possible_duplicate":
            result["review"] += 1
            result["errors"].append({"row": index, "classification": "possible_duplicate",
                                     "similarity_score": score, "existing_record_id": match.id})
            continue
        new_record = Record(name=normalized.name, email=normalized.email, phone=normalized.phone, record_hash=record_hash)
        db.add(new_record)
        db.flush()
        existing_rows.append(new_record)
        result["added"] += 1
    db.commit()
    if result["added"]:
        invalidate("stats:v1")
    return {"status": "completed", **result}


@app.get("/docs-info")
def docs_info():
    return {"api_docs": "/docs", "openapi": "/openapi.json",
            "generated_at": datetime.now(timezone.utc).isoformat(), "auth_enabled": auth_enabled()}
