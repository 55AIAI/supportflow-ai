"""Real PostgreSQL transaction/concurrency contract; enabled explicitly in CI."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from supportflow.api import create_app
from supportflow.config import Settings
from supportflow.db import Database
from supportflow.models import ReturnRequest
from supportflow.worker import run_one


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "PostgreSQL integration configured in CI")
class PostgresTests(unittest.TestCase):
    def test_concurrent_approval_creates_exactly_one_return(self):
        url = os.environ["TEST_DATABASE_URL"]
        from sqlalchemy.engine import make_url
        if make_url(url).database != "supportflow_test":
            raise RuntimeError("Integration requires the dedicated supportflow_test database")
        settings = Settings(database_url=url, secret="ci-only-test-secret-"*3,
                            demo_mode=True, secure_cookie=False)
        database = Database(url)
        app = create_app(settings, database)
        client = TestClient(app)
        session = client.post("/api/demo", json={}, headers={"x-supportflow":"1"}).json()
        org = session["organizations"][0]["id"]
        prefix = "/api/orgs/" + org
        headers = {"x-supportflow":"1","x-csrf-token":session["csrf_token"]}
        ticket = client.get(prefix+"/tickets").json()[0]
        client.post(prefix+"/tickets/"+ticket["id"]+"/analyze", json={}, headers=headers)
        self.assertTrue(run_one(database, settings))
        proposal = client.get(prefix+"/tickets/"+ticket["id"]).json()["proposal"]
        self.assertIsNotNone(proposal)
        cookie = client.cookies.get("sf_session")
        def approve():
            other = TestClient(app)
            other.cookies.set("sf_session", cookie)
            try:
                response = other.post(prefix+"/proposals/"+proposal["id"]+"/approve",
                    json={"fingerprint":proposal["fingerprint"],"confirmed_unused":True},headers=headers)
                return response.status_code, response.json()
            finally:
                other.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _:approve(), range(4)))
        self.assertTrue(all(status==200 for status,_ in results),results)
        self.assertEqual(len({body["id"] for _,body in results}),1)
        with database.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ReturnRequest).where(ReturnRequest.org_id==org)),1)
        client.close()
        database.close()
