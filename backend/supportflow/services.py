import hashlib
import hmac
import json
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .models import Audit, Ticket, Job, Proposal, ReturnRequest, Order, Knowledge, Message, now, uid
from .agent import eligibility


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def scoped(db, model, identifier, org_id, lock=False):
    query = select(model).where(model.id == identifier, model.org_id == org_id)
    if lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Запись не найдена")
    return row


def audit(db, org_id, actor, event, entity_id, detail=None):
    db.add(Audit(org_id=org_id, actor=actor, event=event, entity_id=entity_id, detail=detail or {}))


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def enqueue(db, ticket, actor):
    if ticket.current_job:
        old = db.get(Job, ticket.current_job)
        if old and old.state in ("pending", "running"):
            return old
    identifier, revision = uid(), ticket.version + 1
    result = db.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.version == ticket.version)
                        .values(version=revision, current_job=identifier, status="processing", updated_at=now()))
    if result.rowcount != 1:
        raise HTTPException(409, "Обращение изменилось. Обновите страницу")
    db.execute(update(Proposal).where(Proposal.ticket_id == ticket.id, Proposal.org_id == ticket.org_id,
                                      Proposal.state == "pending").values(state="superseded"))
    job = Job(id=identifier, org_id=ticket.org_id, ticket_id=ticket.id, revision=revision)
    db.add(job)
    audit(db, ticket.org_id, actor, "analysis.queued", ticket.id, {"job_id": identifier})
    return job


def approve(db, proposal_id, org_id, actor, expected_fingerprint, confirmed_unused):
    proposal = scoped(db, Proposal, proposal_id, org_id, lock=True)
    if not hmac.compare_digest(proposal.fingerprint, expected_fingerprint):
        raise HTTPException(409, "Подтверждение относится к другому предложению")
    if proposal.state == "approved":
        existing = db.scalar(select(ReturnRequest).where(ReturnRequest.proposal_id == proposal.id,
                                                         ReturnRequest.org_id == org_id))
        return existing
    if proposal.state != "pending" or proposal.expires_at <= now():
        raise HTTPException(409, "Предложение устарело. Повторите анализ")
    if not confirmed_unused:
        raise HTTPException(422, "Подтвердите проверку состояния товара")
    ticket = scoped(db, Ticket, proposal.ticket_id, org_id, lock=True)
    order = scoped(db, Order, proposal.order_id, org_id, lock=True)
    payload = proposal.payload
    policy = scoped(db, Knowledge, payload["policy_id"], org_id)
    if (ticket.version != payload["ticket_version"] or order.version != payload["order_version"]
            or policy.version != payload["policy_version"]):
        raise HTTPException(409, "Заказ, правила или обращение изменились. Повторите анализ")
    if (order.amount_minor != payload["amount_minor"] or order.currency != payload["currency"]
            or order.id != ticket.order_id):
        raise HTTPException(409, "Данные предложения изменились")
    allowed, reason = eligibility(serialize(order), serialize(ticket), serialize(policy))
    if not allowed:
        raise HTTPException(409, reason)
    claimed = db.execute(update(Proposal).where(Proposal.id == proposal.id, Proposal.state == "pending")
                         .values(state="approved"))
    if claimed.rowcount != 1:
        raise HTTPException(409, "Предложение уже обработано")
    returned = ReturnRequest(org_id=org_id, order_id=order.id, proposal_id=proposal.id, approved_by=actor)
    db.add(returned)
    db.flush()  # unique order and proposal constraints enforce no duplicate action
    order.version += 1
    ticket.version += 1
    ticket.updated_at = now()
    ticket.draft = (f"Здравствуйте! Заявка на возврат заказа №{order.reference} создана. "
                    f"Номер заявки: RET-{returned.id[:8].upper()}. Оператор сообщит дальнейшие инструкции.")
    audit(db, org_id, actor, "return.requested", returned.id, {"proposal_id": proposal.id, "order_id": order.id})
    return returned


def detail(db, ticket, org_id):
    result = serialize(ticket)
    result["messages"] = [serialize(m) for m in db.scalars(
        select(Message).where(Message.org_id == org_id, Message.ticket_id == ticket.id)
        .order_by(Message.created_at, Message.id))]
    result["order"] = serialize(scoped(db, Order, ticket.order_id, org_id)) if ticket.order_id else None
    proposal = db.scalar(select(Proposal).where(Proposal.org_id == org_id, Proposal.ticket_id == ticket.id)
                         .order_by(Proposal.created_at.desc(), Proposal.id.desc()).limit(1))
    result["proposal"] = serialize(proposal) if proposal else None
    job = db.get(Job, ticket.current_job) if ticket.current_job else None
    result["job"] = serialize(job) if job else None
    return result
