import hashlib
import hmac
import secrets
from sqlalchemy import select
from fastapi import HTTPException
from .models import Session, User, Membership, now


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def password_matches(password, value):
    try:
        algorithm, salt, digest = value.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(secret, token):
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def issue_session(db, user_id):
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=token_hash(token), user_id=user_id, expires_at=now() + 8 * 3600))
    return token


def authenticate(db, token):
    session = db.get(Session, token_hash(token or ""))
    if not session or session.expires_at <= now():
        raise HTTPException(401, "Войдите в аккаунт")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def membership(db, org_id, user_id, write=False, owner=False):
    member = db.scalar(select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id))
    if member is None:
        raise HTTPException(404, "Организация не найдена")
    if (owner and member.role != "owner") or (write and member.role not in ("owner", "operator")):
        raise HTTPException(403, "Недостаточно прав")
    return member
