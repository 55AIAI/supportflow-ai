from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


class Database:
    def __init__(self, url):
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 10}
        self.engine = create_engine(url, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def pragmas(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA journal_mode=WAL")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def close(self):
        self.engine.dispose()
