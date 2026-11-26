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
        """)

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
    return name.strip(), email.strip().lower(), service, period, origin

def capture(path, data):
    name, email, service, period, origin = validate(data)
    now = int(time.time())
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT id FROM leads WHERE email=? AND service=?", (email, service)).fetchone()
        if existing:
            return existing["id"], False
        lead_id = str(uuid.uuid4())
        db.execute("INSERT INTO leads(id,name,email,service,period,origin,created) VALUES(?,?,?,?,?,?,?)",
                   (lead_id,name,email,service,period,origin,now))
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
        path=urlsplit(self.path).path
        if path=="/health":
            return self.send(200,{"mode":"local synthetic demo"})
        if not self.authorized():
            return self.send(401,{"error":"Unauthorized"})
        if path=="/metrics":
            return self.send(200,metrics(self.server.db_path))
        if path=="/leads":
            with connect(self.server.db_path) as db:
                rows=[dict(r) for r in db.execute("SELECT * FROM leads ORDER BY created DESC")]
            return self.send(200,{"leads":rows})
        return self.send(404,{"error":"Not found"})

    def do_POST(self):
        if not self.authorized():
            return self.send(401,{"error":"Unauthorized"})
        path=urlsplit(self.path).path
        try:
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
                    updated=db.execute("UPDATE leads SET status=? WHERE id=?",(data["status"],lead_id)).rowcount
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
    server=ThreadingHTTPServer(("127.0.0.1",8765),Handler)
    server.db_path=path
    server.token=token
    print("Local synthetic demo API: http://127.0.0.1:8765 (no production use)")
    server.serve_forever()

if __name__=="__main__":
    main()
