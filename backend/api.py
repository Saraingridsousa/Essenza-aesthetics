"""Local-only synthetic lead API. No external requests, no production deployment."""
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from backend import assistant

SERVICES = ("Limpeza de pele", "Massagem facial", "Hidratação facial", "Drenagem linfática", "Cuidados corporais", "Massagem relaxante", "Avaliação geral")
STATUSES = ("Novo", "Em contato", "Agendado", "Convertido")
PERIODS = ("Sem preferência", "Manhã", "Tarde", "Noite")
ORIGINS = ("Formulário", "Card de procedimento", "CTA de avaliação", "API de teste")
MAX_ATTEMPTS = 5

@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()

def init(path):
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
          service TEXT NOT NULL, period TEXT NOT NULL, origin TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Novo', created INTEGER NOT NULL,
          UNIQUE(email, service));
        CREATE TABLE IF NOT EXISTS outbox (
          id TEXT PRIMARY KEY, lead_id TEXT NOT NULL REFERENCES leads(id),
          service TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0, available INTEGER NOT NULL,
          lease TEXT, UNIQUE(lead_id));
        CREATE TABLE IF NOT EXISTS status_history (
          id INTEGER PRIMARY KEY, lead_id TEXT NOT NULL REFERENCES leads(id),
          from_status TEXT NOT NULL, to_status TEXT NOT NULL, changed INTEGER NOT NULL);
        """)
        columns={row[1] for row in db.execute("PRAGMA table_info(leads)")}
        if "campaign" not in columns:
            db.execute("ALTER TABLE leads ADD COLUMN campaign TEXT NOT NULL DEFAULT 'Direto'")

def validate(data):
    if not isinstance(data, dict) or data.get("consent") is not True:
        raise ValueError("Explicit demo consent required")
    name, email, service = (data.get(k) for k in ("name", "email", "service"))
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 70:
        raise ValueError("Invalid fictional name")
    if not isinstance(email, str) or len(email) > 100 or not re.fullmatch(r"[^\s@]+@example\.(com|org|net)", email.strip(), re.I):
        raise ValueError("Only reserved example.com/.org/.net emails are accepted")
    period = data.get("period") or "Sem preferência"
    origin = data.get("origin", "API de teste")
    if service not in SERVICES or period not in PERIODS or origin not in ORIGINS:
        raise ValueError("Invalid service, period or origin")
    campaign=data.get("campaign","Direto")
    if campaign not in ("Instagram","Google","Indicação","Direto"):
        raise ValueError("Invalid campaign")
    return name.strip(), email.strip().lower(), service, period, origin, campaign

def capture(path, data):
    name, email, service, period, origin, campaign = validate(data)
    now = int(time.time())
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id FROM leads WHERE email=? AND service=?", (email, service)).fetchone()
        if existing:
            return existing["id"], False
        lead_id = str(uuid.uuid4())
        db.execute("INSERT INTO leads(id,name,email,service,period,origin,created,campaign) VALUES(?,?,?,?,?,?,?,?)",
                   (lead_id,name,email,service,period,origin,now,campaign))
        db.execute("INSERT INTO outbox(id,lead_id,service,available) VALUES(?,?,?,?)",
                   (str(uuid.uuid4()),lead_id,service,now))
        return lead_id, True

def claim(path, now=None):
    now = int(time.time()) if now is None else now
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE outbox SET state='failed',lease=NULL WHERE state='processing' AND available<=? AND attempts>=?", (now,MAX_ATTEMPTS))
        row = db.execute("""SELECT id,lead_id,service,attempts FROM outbox
          WHERE (state='pending' OR state='processing') AND available<=? AND attempts<?
          ORDER BY available,id LIMIT 1""", (now,MAX_ATTEMPTS)).fetchone()
        if not row:
            return None
        lease = str(uuid.uuid4())
        db.execute("UPDATE outbox SET state='processing',attempts=attempts+1,available=?,lease=? WHERE id=?", (now+120,lease,row["id"]))
        return {**dict(row),"attempts":row["attempts"]+1,"lease":lease}

def finish(path, event_id, lease, success, now=None):
    now = int(time.time()) if now is None else now
    if not isinstance(lease,str) or not isinstance(success,bool):
        raise ValueError("Invalid acknowledgement")
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT attempts FROM outbox WHERE id=? AND state='processing' AND lease=? AND available>?", (event_id,lease,now)).fetchone()
        if not row:
            return False
        state = "sent" if success else ("failed" if row["attempts"]>=MAX_ATTEMPTS else "pending")
        db.execute("UPDATE outbox SET state=?,available=?,lease=NULL WHERE id=?",
                   (state,now+min(300,2**row["attempts"]),event_id))
        return True

def metrics(path):
    with connect(path) as db:
        total=db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        states={s:0 for s in STATUSES}
        states.update({r[0]:r[1] for r in db.execute("SELECT status,COUNT(*) FROM leads GROUP BY status")})
        queue={r[0]:r[1] for r in db.execute("SELECT state,COUNT(*) FROM outbox GROUP BY state")}
        return {"total":total,"statuses":states,"converted_share":round(states["Convertido"]/total,4) if total else None,"outbox":queue}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass  # Avoid logging demo names, email addresses or tokens.

    def send(self,code,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def local_host(self):
        port = self.server.server_address[1]
        expected = f"127.0.0.1:{port}"
        return self.headers.get("Host") == expected and self.headers.get("Origin") in (None, "http://" + expected)

    def static(self, path):
        root = Path(__file__).resolve().parents[1]
        allowed = {"/": ("index.html", "text/html; charset=utf-8"),
                   "/index.html": ("index.html", "text/html; charset=utf-8"),
                   "/assets/essenza-mark.svg": ("assets/essenza-mark.svg", "image/svg+xml"),
                   "/assets/photos/room.webp": ("assets/photos/room.webp", "image/webp"),
                   "/assets/photos/towels.webp": ("assets/photos/towels.webp", "image/webp"),
                   "/assets/photos/cleansing.webp": ("assets/photos/cleansing.webp", "image/webp"),
                   "/assets/photos/facial-massage.webp": ("assets/photos/facial-massage.webp", "image/webp"),
                   "/assets/photos/hydration.webp": ("assets/photos/hydration.webp", "image/webp"),
                   "/assets/photos/drainage.webp": ("assets/photos/drainage.webp", "image/webp"),
                   "/assets/photos/bodycare.webp": ("assets/photos/bodycare.webp", "image/webp"),
                   "/assets/photos/relaxing.webp": ("assets/photos/relaxing.webp", "image/webp"),
                   "/assets/photos/about-space.webp": ("assets/photos/about-space.webp", "image/webp"),
                   "/assets/photos/skincare.webp": ("assets/photos/skincare.webp", "image/webp"),
                   "/assets/photos/reception.webp": ("assets/photos/reception.webp", "image/webp"),
                   "/assets/photos/team-care.webp": ("assets/photos/team-care.webp", "image/webp"),
                   "/assets/photos/experience.webp": ("assets/photos/experience.webp", "image/webp"),
                   "/assets/photos/cta-room.webp": ("assets/photos/cta-room.webp", "image/webp"),
                   "/assets/photos/about-neutral.webp": ("assets/photos/about-neutral.webp", "image/webp"),
                   "/assets/photos/cta-neutral.webp": ("assets/photos/cta-neutral.webp", "image/webp"),
                   "/assets/social/og-cover.jpg": ("assets/social/og-cover.jpg", "image/jpeg")}
        if path not in allowed:
            return False
        relative, content_type = allowed[path]
        file=root / relative
        if not file.is_file():
            self.send(404,{"error":"Asset not available"})
            return True
        body = file.read_bytes()
        if relative == "index.html":
            body = body.replace(b'<html lang="pt-BR">', b'<html lang="pt-BR" data-local-demo="true">', 1)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def authorized(self):
        supplied=self.headers.get("Authorization","")
        return hmac.compare_digest(supplied.encode(),("Bearer "+self.server.token).encode())

    def payload(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=8192:
                raise ValueError("Invalid body size")
            return json.loads(self.rfile.read(size))
        except (ValueError,UnicodeError):
            raise ValueError("Invalid JSON body")

    def do_GET(self):
        if not self.local_host():
            return self.send(403,{"error":"Local host only"})
        path=urlsplit(self.path).path
        if self.static(path):
            return
        if path=="/health":
            return self.send(200,{"mode":"local synthetic demo"})
        if not self.authorized():
            return self.send(401,{"error":"Unauthorized"})
        if path=="/metrics":
            return self.send(200,metrics(self.server.db_path))
        if path=="/leads":
            with connect(self.server.db_path) as db:
                rows=[dict(r) for r in db.execute("SELECT * FROM leads ORDER BY created DESC")]
                history={}
                for item in db.execute("SELECT lead_id,from_status,to_status,changed FROM status_history ORDER BY id"):
                    history.setdefault(item["lead_id"],[]).append(dict(item))
                for row in rows:
                    row["history"]=history.get(row["id"],[])
            return self.send(200,{"leads":rows})
        return self.send(404,{"error":"Not found"})

    def do_POST(self):
        if not self.local_host():
            return self.send(403,{"error":"Local host only"})
        if not self.authorized():
            return self.send(401,{"error":"Unauthorized"})
        path=urlsplit(self.path).path
        try:
            if path=="/assistant":
                data=self.payload()
                if not isinstance(data,dict):
                    raise ValueError("Invalid topic")
                return self.send(200,assistant.answer(data.get("topic")))
            if path=="/leads":
                lead_id,created=capture(self.server.db_path,self.payload())
                return self.send(201 if created else 200,{"id":lead_id,"created":created})
            if path=="/outbox/claim":
                return self.send(200,{"event":claim(self.server.db_path)})
            if path=="/outbox/ack":
                data=self.payload()
                if not isinstance(data,dict) or not isinstance(data.get("id"),str):
                    raise ValueError("Invalid event")
                ok=finish(self.server.db_path,data["id"],data.get("lease"),data.get("success"))
                return self.send(200 if ok else 409,{"accepted":ok})
            if path.startswith("/leads/") and path.endswith("/status"):
                lead_id=path.split("/")[2]
                data=self.payload()
                if not isinstance(data,dict) or data.get("status") not in STATUSES:
                    raise ValueError("Invalid status")
                with connect(self.server.db_path) as db:
                    db.execute("BEGIN IMMEDIATE")
                    old=db.execute("SELECT status FROM leads WHERE id=?",(lead_id,)).fetchone()
                    updated=bool(old)
                    if old and old["status"]!=data["status"]:
                        db.execute("UPDATE leads SET status=? WHERE id=?",(data["status"],lead_id))
                        db.execute("INSERT INTO status_history(lead_id,from_status,to_status,changed) VALUES(?,?,?,?)",(lead_id,old["status"],data["status"],int(time.time())))
                return self.send(200 if updated else 404,{"updated":bool(updated)})
            return self.send(404,{"error":"Not found"})
        except ValueError as e:
            return self.send(400,{"error":str(e)})

def main():
    token=os.environ.get("ESSENZA_DEMO_TOKEN","")
    if len(token)<24:
        raise SystemExit("Set ESSENZA_DEMO_TOKEN to a random token of at least 24 characters.")
    path=Path(os.environ.get("ESSENZA_DB","essenza-demo.sqlite3"))
    init(path)
    # Container port is published only to the host loopback by compose.yaml.
    bind="0.0.0.0" if os.environ.get("ESSENZA_CONTAINER")=="1" else "127.0.0.1"
    server=ThreadingHTTPServer((bind,8765),Handler)
    server.db_path=path
    server.token=token
    print("Local synthetic demo API: http://127.0.0.1:8765 (no production use)")
    server.serve_forever()

if __name__=="__main__":
    main()
