from dataclasses import dataclass
import os
import secrets


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./supportflow.db"
    secret: str = ""
    demo_mode: bool = False
    inline_worker: bool = False
    provider: str = "demo"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    secure_cookie: bool = True
    app_origin: str = ""

    @classmethod
    def from_env(cls):
        demo = os.getenv("SUPPORTFLOW_DEMO", "0") == "1"
        secret = os.getenv("APP_SECRET", "")
        if not secret and demo:
            secret = secrets.token_urlsafe(48)
        if len(secret.encode()) < 32:
            raise ValueError("APP_SECRET must contain at least 32 bytes")
        provider = os.getenv("AI_PROVIDER", "demo")
        if provider not in {"demo", "ollama"}:
            raise ValueError("AI_PROVIDER must be demo or ollama")
        return cls(database_url=os.getenv("DATABASE_URL", "sqlite:///./supportflow.db"),
                   secret=secret, demo_mode=demo,
                   inline_worker=os.getenv("INLINE_WORKER", "0") == "1",
                   provider=provider,
                   ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
                   ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
                   secure_cookie=os.getenv("COOKIE_SECURE", "1") == "1",
                   app_origin=os.getenv("APP_ORIGIN", "").rstrip("/"))
