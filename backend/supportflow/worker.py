"""Database-backed jobs with leases, bounded retries and guarded publication."""
import logging
import threading
from sqlalchemy import and_, or_, select, update
from .models import Job, Ticket, Order, Knowledge, Proposal, ReturnRequest, now, uid
from .services import serialize, fingerprint, audit
from .agent import generate, ProviderUnavailable

LOG = logging.getLogger(__name__)


def run_one(database, settings):
    timestamp = now()
    with database.sessions.begin() as db:
        exhausted = list(db.scalars(select(Job).where(
            Job.state == "running", Job.lease_until <= timestamp, Job.attempts >= 3).limit(20)))
        for job in exhausted:
            job.state, job.error, job.finished_at = "failed", "lease_exhausted", timestamp
            ticket = db.get(Ticket, job.ticket_id)
            if ticket and ticket.current_job == job.id:
                ticket.status = "failed"
        condition = and_(Job.attempts < 3, or_(
            and_(Job.state == "pending", Job.available_at <= timestamp),
            and_(Job.state == "running", Job.lease_until <= timestamp)))
        job = db.scalar(select(Job).where(condition).order_by(Job.created_at, Job.id).limit(1))
        if job is None:
            return False
        token = uid()
        changed = db.execute(update(Job).where(Job.id == job.id, condition,
                                                Job.lease_token == job.lease_token)
                             .values(state="running", attempts=Job.attempts + 1,
                                     lease_token=token, lease_until=timestamp + 60))
        if changed.rowcount != 1:
            return False
        identifier = job.id
    with database.sessions() as db:
        job = db.get(Job, identifier)
        ticket = db.get(Ticket, job.ticket_id)
        if ticket is None:
            return False
        order = db.get(Order, ticket.order_id) if ticket.order_id else None
        if order and order.org_id != job.org_id:
            order = None
        documents = list(db.scalars(select(Knowledge).where(Knowledge.org_id == job.org_id)))
        context = {"ticket": serialize(ticket), "order": serialize(order) if order else None,
                   "documents": [serialize(d) for d in documents]}
        exists = bool(order and db.scalar(select(ReturnRequest.id).where(
            ReturnRequest.org_id == job.org_id, ReturnRequest.order_id == order.id)))
    try:
        result = generate(context, settings)
        if exists:
            result["propose_return"] = False
            result["escalation"] = "По этому заказу уже создана заявка на возврат"
        with database.sessions.begin() as db:
            job = db.scalar(select(Job).where(Job.id == identifier).with_for_update())
            if job.lease_token != token or job.state != "running":
                return True
            ticket = db.scalar(select(Ticket).where(Ticket.id == job.ticket_id).with_for_update())
            if ticket.current_job != identifier or ticket.version != job.revision:
                job.state, job.finished_at = "superseded", now()
                return True
            changed = db.execute(update(Ticket).where(
                Ticket.id == ticket.id, Ticket.version == job.revision, Ticket.current_job == identifier)
                .values(category=result["category"], draft=result["answer"],
                        sources=result["sources"], escalation=result["escalation"],
                        version=Ticket.version + 1, updated_at=now(), status="review"))
            if changed.rowcount != 1:
                job.state, job.finished_at = "superseded", now()
                return True
            db.refresh(ticket)
            if result["propose_return"]:
                order = context["order"]
                policy = next(d for d in context["documents"] if d["kind"] == "returns")
                payload = {"action": "create_return_request", "order_id": order["id"],
                           "order_reference": order["reference"], "amount_minor": order["amount_minor"],
                           "currency": order["currency"], "order_version": order["version"],
                           "policy_id": policy["id"], "policy_version": policy["version"],
                           "ticket_version": ticket.version}
                db.add(Proposal(org_id=job.org_id, ticket_id=ticket.id, order_id=order["id"],
                                payload=payload, fingerprint=fingerprint(payload), expires_at=now() + 900))
            job.state, job.finished_at, job.error = "completed", now(), ""
            audit(db, job.org_id, "worker", "analysis.completed", ticket.id,
                  {"job_id": identifier, "provider": result["provider"], "usage": result["usage"]})
    except Exception as error:
        code = "provider_unavailable" if isinstance(error, ProviderUnavailable) else "analysis_failed"
        LOG.warning("job_failed job_id=%s code=%s", identifier, code)
        with database.sessions.begin() as db:
            job = db.scalar(select(Job).where(Job.id == identifier).with_for_update())
            if job.lease_token != token or job.state != "running":
                return True
            job.error = code
            job.state = "failed" if job.attempts >= 3 else "pending"
            job.available_at, job.lease_until = now() + 2 ** job.attempts, 0
            if job.state == "failed":
                job.finished_at = now()
                ticket = db.get(Ticket, job.ticket_id)
                if ticket and ticket.current_job == identifier:
                    ticket.status = "failed"
                    audit(db, job.org_id, "worker", "analysis.failed", ticket.id, {"code": code})
    return True


def serve(database, settings, stop):
    while not stop.is_set():
        try:
            worked = run_one(database, settings)
        except Exception:
            LOG.exception("worker_database_error")
            worked = False
        stop.wait(.1 if worked else 1)


def main():
    import signal
    from .config import Settings
    from .db import Database
    settings = Settings.from_env()
    database, stop = Database(settings.database_url), threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *args: stop.set())
    try:
        serve(database, settings, stop)
    finally:
        database.close()


if __name__ == "__main__":
    main()
