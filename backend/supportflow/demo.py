"""Start a local sandbox with an inline worker; no credentials or LLM required."""
import os
from pathlib import Path
import uvicorn
from .config import Settings
from .db import Database
from .models import Base
from .api import create_app


def main():
    os.environ.setdefault("SUPPORTFLOW_DEMO", "1")
    os.environ.setdefault("COOKIE_SECURE", "0")
    os.environ.setdefault("INLINE_WORKER", "1")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/demo.db")
    Path("data").mkdir(exist_ok=True)
    settings = Settings.from_env()
    database = Database(settings.database_url)
    Base.metadata.create_all(database.engine)  # explicit demo convenience; production uses Alembic
    uvicorn.run(create_app(settings, database), host="127.0.0.1",
                port=int(os.getenv("PORT", "5080")), access_log=False)


if __name__ == "__main__":
    main()
