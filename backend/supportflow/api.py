import asyncio
from contextlib import asynccontextmanager
from collections import OrderedDict
import hmac
import json
import logging
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, delete, text, func
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .db import Database
from .models import (Base, Organization, User, Membership, Session, Order, Knowledge,
                     Ticket, Message, Job, Proposal, ReturnRequest, Audit, now, uid)
from .security import (password_hash, password_matches, issue_session, token_hash,
                       csrf_token, authenticate, membership)
from .schemas import Login, Register, RoleInput, CreateTicket, Approval, Reply, KnowledgeInput
from .services import scoped, serialize, audit, enqueue, approve, detail
from .seed import seed_organization, return_text

LOG = logging.getLogger("supportflow")


def create_app(settings: Settings, database=None):
    database = database or Database(settings.database_url)
    if len(settings.secret.encode()) < 32:
        raise ValueError("APP_SECRET must contain at least 32 bytes")

    @asynccontextmanager
    async def lifespan(app):
        stop, thread = threading.Event(), None
        if settings.inline_worker:
            from .worker import serve
            thread = threading.Thread(target=serve, args=(database, settings, stop), daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(30)
        database.close()

    app = FastAPI(title="SupportFlow AI", version="0.1.0", lifespan=lifespan)
    app.state.database, app.state.settings = database, settings
    attempts = OrderedDict()
    limiter_lock = threading.Lock()
    dummy_hash = password_hash("invalid-password-for-timing")

    def throttle(request):
        key, timestamp = request.client.host if request.client else "unknown", time.monotonic()
        with limiter_lock:
            prior = attempts.get(key, [])
            prior = [t for t in prior if t > timestamp - 300]
            if len(prior) >= 20:
                raise HTTPException(429, "Слишком много попыток. Повторите позже", headers={"Retry-After": "300"})
            attempts[key] = prior + [timestamp]
            attempts.move_to_end(key)
            while len(attempts) > 10000:
                attempts.popitem(last=False)

    @app.middleware("http")
    async def boundaries(request, call_next):
        request_id = uid()
        if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            length = request.headers.get("content-length")
            if length is None:
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            if not length.isdecimal() or int(length) > 65536:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
            if request.headers.get("x-supportflow") != "1":
                return JSONResponse({"detail": "Missing request header"}, status_code=403)
            origin = request.headers.get("origin")
            expected = settings.app_origin or str(request.base_url).rstrip("/")
            if origin and origin.rstrip("/") != expected:
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
            if request.url.path not in ("/api/auth/login", "/api/auth/register", "/api/demo"):
                token = request.cookies.get("sf_session", "")
                expected_csrf = csrf_token(settings.secret, token)
                if not token or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), expected_csrf):
                    return JSONResponse({"detail": "CSRF check failed"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(IntegrityError)
    async def conflict(request, error):
        return JSONResponse({"detail": "Запись уже существует или была изменена. Обновите страницу"}, status_code=409)

    def session_db(request: Request):
        with database.sessions() as db:
            if request.method not in ("GET", "HEAD", "OPTIONS") and database.engine.dialect.name == "sqlite":
                db.execute(text("BEGIN IMMEDIATE"))
            yield db

    def current_user(request: Request, db=Depends(session_db)):
        return authenticate(db, request.cookies.get("sf_session"))

    def auth_result(db, user, token):
        organizations = []
        for member in db.scalars(select(Membership).where(Membership.user_id == user.id)):
            org = db.get(Organization, member.org_id)
            organizations.append({"id": org.id, "name": org.name, "role": member.role, "is_demo": org.is_demo})
        return {"user": {"id": user.id, "name": user.name, "email": user.email},
                "organizations": organizations, "csrf_token": csrf_token(settings.secret, token)}

    def logged_in(db, user):
        token = issue_session(db, user.id)
        db.commit()
        response = JSONResponse(auth_result(db, user, token))
        response.set_cookie("sf_session", token, max_age=8 * 3600, httponly=True,
                            secure=settings.secure_cookie, samesite="strict", path="/")
        return response

    @app.get("/api/config")
    def configuration(request: Request, db=Depends(session_db)):
        try:
            authenticate(db, request.cookies.get("sf_session"))
            authenticated = True
        except HTTPException:
            authenticated = False
        return {"demo_available": settings.demo_mode, "provider": settings.provider,
                "authenticated": authenticated}

    @app.get("/api/orgs/{org_id}/checks")
    def checks(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        from .evals import run_checks
        return run_checks()

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(db=Depends(session_db)):
        try:
            db.execute(text("SELECT 1"))
            db.execute(select(Organization.id).limit(1))
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    @app.post("/api/auth/register")
    def register(body: Register, request: Request, db=Depends(session_db)):
        throttle(request)
        user = User(email=body.email, name=body.name, password_hash=password_hash(body.password))
        org = Organization(name=body.organization, is_demo=False)
        db.add_all([user, org])
        db.flush()
        db.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
        audit(db, org.id, user.id, "organization.created", org.id)
        return logged_in(db, user)

    @app.post("/api/auth/login")
    def login(body: Login, request: Request, db=Depends(session_db)):
        throttle(request)
        user = db.scalar(select(User).where(User.email == body.email))
        encoded = user.password_hash if user else dummy_hash
        if not password_matches(body.password, encoded) or user is None:
            raise HTTPException(401, "Неверный email или пароль")
        return logged_in(db, user)

    @app.get("/api/auth/session")
    def session(request: Request, user=Depends(current_user), db=Depends(session_db)):
        return auth_result(db, user, request.cookies["sf_session"])

    @app.post("/api/auth/logout")
    def logout(request: Request, user=Depends(current_user), db=Depends(session_db)):
        db.execute(delete(Session).where(Session.token_hash == token_hash(request.cookies["sf_session"])))
        db.commit()
        response = JSONResponse({"ok": True})
        response.delete_cookie("sf_session", path="/", secure=settings.secure_cookie,
                               httponly=True, samesite="strict")
        return response

    @app.post("/api/demo")
    def demo(body: RoleInput, request: Request, db=Depends(session_db)):
        if not settings.demo_mode:
            raise HTTPException(404, "Демо отключено")
        throttle(request)
        user = User(email=uid() + "@example.test", name="Оператор Демо",
                    password_hash=password_hash(secrets.token_urlsafe(40)))
        db.add(user)
        db.flush()
        seed_organization(db, user.id, role=body.role)
        seed_organization(db, user.id, name="North Supply", days=30, role=body.role)
        return logged_in(db, user)

    @app.post("/api/orgs/{org_id}/demo-role")
    def demo_role(org_id: str, body: RoleInput, user=Depends(current_user), db=Depends(session_db)):
        member = membership(db, org_id, user.id)
        if not settings.demo_mode or not db.get(Organization, org_id).is_demo:
            raise HTTPException(404, "Демо отключено")
        member.role = body.role
        db.commit()
        return {"role": member.role}

    @app.get("/api/orgs/{org_id}/tickets")
    def tickets(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        return [serialize(t) for t in db.scalars(select(Ticket).where(Ticket.org_id == org_id)
                                                .order_by(Ticket.created_at.desc(), Ticket.id).limit(200))]

    @app.post("/api/orgs/{org_id}/tickets", status_code=201)
    def create_ticket(org_id: str, body: CreateTicket, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, write=True)
        order = None
        if body.order_reference:
            order = db.scalar(select(Order).where(Order.org_id == org_id, Order.reference == body.order_reference))
            if order is None or order.customer_key != body.customer_key:
                raise HTTPException(422, "Заказ не принадлежит указанному клиенту")
        ticket = Ticket(org_id=org_id, subject=body.subject, customer_name=body.customer_name,
                        customer_key=body.customer_key, message=body.message, order_id=order.id if order else None)
        db.add(ticket)
        db.flush()
        db.add(Message(org_id=org_id, ticket_id=ticket.id, author="customer", body=body.message))
        audit(db, org_id, user.id, "ticket.created", ticket.id)
        db.commit()
        return detail(db, ticket, org_id)

    @app.get("/api/orgs/{org_id}/tickets/{ticket_id}")
    def ticket(org_id: str, ticket_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        return detail(db, scoped(db, Ticket, ticket_id, org_id), org_id)

    @app.post("/api/orgs/{org_id}/tickets/{ticket_id}/analyze", status_code=202)
    def analyze(org_id: str, ticket_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, write=True)
        ticket = scoped(db, Ticket, ticket_id, org_id, lock=True)
        job = enqueue(db, ticket, user.id)
        db.commit()
        return serialize(job)

    @app.post("/api/orgs/{org_id}/proposals/{proposal_id}/approve")
    def approve_proposal(org_id: str, proposal_id: str, body: Approval,
                         user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, write=True)
        returned = approve(db, proposal_id, org_id, user.id, body.fingerprint, body.confirmed_unused)
        db.commit()
        return serialize(returned)

    @app.post("/api/orgs/{org_id}/proposals/{proposal_id}/reject")
    def reject(org_id: str, proposal_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, write=True)
        proposal = scoped(db, Proposal, proposal_id, org_id, lock=True)
        if proposal.state != "pending":
            raise HTTPException(409, "Предложение уже обработано")
        proposal.state = "rejected"
        audit(db, org_id, user.id, "proposal.rejected", proposal.id)
        db.commit()
        return {"ok": True}

    @app.post("/api/orgs/{org_id}/tickets/{ticket_id}/reply")
    def reply(org_id: str, ticket_id: str, body: Reply, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, write=True)
        ticket = scoped(db, Ticket, ticket_id, org_id, lock=True)
        db.add(Message(org_id=org_id, ticket_id=ticket.id, author="operator", body=body.body))
        ticket.version, ticket.updated_at, ticket.status = ticket.version + 1, now(), "closed"
        audit(db, org_id, user.id, "reply.saved", ticket.id)
        db.commit()
        return detail(db, ticket, org_id)

    @app.get("/api/orgs/{org_id}/orders")
    def orders(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        return [serialize(o) for o in db.scalars(select(Order).where(Order.org_id == org_id).limit(200))]

    @app.get("/api/orgs/{org_id}/knowledge")
    def knowledge(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        return [serialize(d) for d in db.scalars(select(Knowledge).where(Knowledge.org_id == org_id)
                                                .order_by(Knowledge.kind))]

    @app.put("/api/orgs/{org_id}/knowledge")
    def save_knowledge(org_id: str, body: KnowledgeInput, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id, owner=True)
        document = db.scalar(select(Knowledge).where(Knowledge.org_id == org_id,
                                                     Knowledge.kind == body.kind).with_for_update())
        if document and body.expected_version != document.version:
            raise HTTPException(409, "Правила изменились. Обновите страницу")
        if body.kind == "returns" and body.return_days is None:
            raise HTTPException(422, "Укажите срок возврата")
        text_body = return_text(body.return_days) if body.kind == "returns" else body.body
        if not text_body:
            raise HTTPException(422, "Укажите текст правил")
        if document is None:
            document = Knowledge(org_id=org_id, kind=body.kind, version=1)
            db.add(document)
        else:
            document.version += 1
        document.title, document.body = body.title, text_body
        document.return_days, document.updated_at = body.return_days if body.kind == "returns" else None, now()
        db.flush()
        audit(db, org_id, user.id, "knowledge.updated", document.id, {"version": document.version})
        db.commit()
        return serialize(document)

    @app.get("/api/orgs/{org_id}/audit")
    def history(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        return [serialize(a) for a in db.scalars(select(Audit).where(Audit.org_id == org_id)
                                                .order_by(Audit.created_at.desc(), Audit.id.desc()).limit(200))]

    @app.get("/api/orgs/{org_id}/metrics")
    def metrics(org_id: str, user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        def count(model, *filters):
            return db.scalar(select(func.count()).select_from(model).where(model.org_id == org_id, *filters))
        return {"tickets": count(Ticket), "pending_jobs": count(Job, Job.state.in_(["pending", "running"])),
                "failed_jobs": count(Job, Job.state == "failed"), "return_requests": count(ReturnRequest),
                "provider": settings.provider}

    @app.get("/api/orgs/{org_id}/tickets/{ticket_id}/events")
    async def events(org_id: str, ticket_id: str, request: Request,
                     user=Depends(current_user), db=Depends(session_db)):
        membership(db, org_id, user.id)
        scoped(db, Ticket, ticket_id, org_id)
        user_id, session_token = user.id, request.cookies["sf_session"]

        async def stream():
            previous = None
            for _ in range(60):
                if await request.is_disconnected():
                    return
                with database.sessions() as fresh:
                    try:
                        authenticate(fresh, session_token)
                        membership(fresh, org_id, user_id)
                        ticket = scoped(fresh, Ticket, ticket_id, org_id)
                    except HTTPException:
                        return
                    job = fresh.get(Job, ticket.current_job) if ticket.current_job else None
                    state = {"version": ticket.version, "status": ticket.status,
                             "job_state": job.state if job else None}
                if state != previous:
                    yield "event: ticket\ndata: " + json.dumps(state) + "\n\n"
                    previous = state
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")
        @app.get("/")
        def index():
            return FileResponse(frontend / "index.html")
        @app.get("/favicon.ico", include_in_schema=False)
        def favicon():
            return JSONResponse(None, status_code=204)
    return app
