import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from supportflow.api import create_app
from supportflow.config import Settings
from supportflow.db import Database
from supportflow.models import Base, Proposal, ReturnRequest, Knowledge, Order, Job, Ticket, now
from supportflow.worker import run_one


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(database_url="sqlite:///" + str(Path(self.tmp.name) / "test.db"),
                                 secret="test-secret-" * 5, demo_mode=True, secure_cookie=False)
        self.db = Database(self.settings.database_url)
        Base.metadata.create_all(self.db.engine)
        self.app = create_app(self.settings, self.db)
        self.client = TestClient(self.app)
        response = self.client.post("/api/demo", json={"role": "operator"}, headers={"x-supportflow": "1"})
        self.assertEqual(response.status_code, 200, response.text)
        self.session = response.json()
        self.org = self.session["organizations"][0]["id"]
        self.other_org = self.session["organizations"][1]["id"]
        self.headers = {"x-supportflow": "1", "x-csrf-token": self.session["csrf_token"]}
        self.tickets = self.client.get(self.url("/tickets")).json()
        self.ticket = self.tickets[0]

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.tmp.cleanup()

    def url(self, suffix, org=None):
        return "/api/orgs/" + (org or self.org) + suffix

    def post(self, suffix, body=None, org=None):
        return self.client.post(self.url(suffix, org), json=body or {}, headers=self.headers)

    def analyzed(self):
        response = self.post("/tickets/" + self.ticket["id"] + "/analyze")
        self.assertEqual(response.status_code, 202, response.text)
        self.assertTrue(run_one(self.db, self.settings))
        detail = self.client.get(self.url("/tickets/" + self.ticket["id"])).json()
        self.assertEqual(detail["job"]["state"], "completed", detail)
        return detail

    def approve(self, proposal, **updates):
        body = {"fingerprint": proposal["fingerprint"], "confirmed_unused": True}
        body.update(updates)
        return self.post("/proposals/" + proposal["id"] + "/approve", body)

    def test_return_flow_and_idempotency(self):
        detail = self.analyzed()
        proposal = detail["proposal"]
        self.assertIsNotNone(proposal)
        first, second = self.approve(proposal), self.approve(proposal)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["id"], second.json()["id"])
        with self.db.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ReturnRequest)), 1)

    def test_cross_tenant_read_and_actions_are_hidden(self):
        detail = self.analyzed()
        self.assertEqual(self.client.get(self.url("/tickets/" + self.ticket["id"], self.other_org)).status_code, 404)
        result = self.post("/proposals/" + detail["proposal"]["id"] + "/approve",
                           {"fingerprint": detail["proposal"]["fingerprint"], "confirmed_unused": True},
                           self.other_org)
        self.assertEqual(result.status_code, 404)
        with TestClient(self.app) as stranger:
            stranger.post("/api/demo", json={}, headers={"x-supportflow": "1"})
            self.assertEqual(stranger.get(self.url("/tickets")).status_code, 404)

    def test_viewer_cannot_mutate(self):
        self.post("/demo-role", {"role": "viewer"})
        self.assertEqual(self.post("/tickets/" + self.ticket["id"] + "/analyze").status_code, 403)
        self.assertEqual(self.post("/tickets/" + self.ticket["id"] + "/reply", {"body": "hello"}).status_code, 403)
        self.assertEqual(self.client.get(self.url("/tickets")).status_code, 200)

    def test_operator_cannot_edit_knowledge(self):
        result = self.client.put(self.url("/knowledge"), json={"kind": "returns", "title": "Policy",
                                                             "return_days": 30}, headers=self.headers)
        self.assertEqual(result.status_code, 403)

    def test_owner_updates_policy_and_old_approval_is_rejected(self):
        detail = self.analyzed()
        self.post("/demo-role", {"role": "owner"})
        policy = next(d for d in self.client.get(self.url("/knowledge")).json() if d["kind"] == "returns")
        result = self.client.put(self.url("/knowledge"), json={
            "kind": "returns", "title": policy["title"], "return_days": 3,
            "expected_version": policy["version"]}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.approve(detail["proposal"]).status_code, 409)

    def test_changed_order_blocks_proposal(self):
        detail = self.analyzed()
        with self.db.sessions.begin() as db:
            order = db.get(Order, detail["order"]["id"])
            order.version += 1
        self.assertEqual(self.approve(detail["proposal"]).status_code, 409)

    def test_expired_proposal_blocks_action(self):
        detail = self.analyzed()
        with self.db.sessions.begin() as db:
            db.get(Proposal, detail["proposal"]["id"]).expires_at = now() - 1
        self.assertEqual(self.approve(detail["proposal"]).status_code, 409)

    def test_fingerprint_and_unused_confirmation_required(self):
        proposal = self.analyzed()["proposal"]
        self.assertEqual(self.approve(proposal, fingerprint="0" * 64).status_code, 409)
        self.assertEqual(self.approve(proposal, confirmed_unused=False).status_code, 422)

    def test_rejected_proposal_cannot_execute(self):
        proposal = self.analyzed()["proposal"]
        self.assertEqual(self.post("/proposals/" + proposal["id"] + "/reject").status_code, 200)
        self.assertEqual(self.approve(proposal).status_code, 409)

    def test_duplicate_analysis_reuses_active_job(self):
        a = self.post("/tickets/" + self.ticket["id"] + "/analyze")
        b = self.post("/tickets/" + self.ticket["id"] + "/analyze")
        self.assertEqual(a.json()["id"], b.json()["id"])

    def test_reply_invalidates_pending_analysis_result(self):
        self.post("/tickets/" + self.ticket["id"] + "/analyze")
        self.post("/tickets/" + self.ticket["id"] + "/reply", {"body": "Manual response"})
        run_one(self.db, self.settings)
        detail = self.client.get(self.url("/tickets/" + self.ticket["id"])).json()
        self.assertEqual(detail["job"]["state"], "superseded")
        self.assertIsNone(detail["proposal"])

    def test_lease_recovery_and_bounded_attempts(self):
        response = self.post("/tickets/" + self.ticket["id"] + "/analyze")
        with self.db.sessions.begin() as db:
            job = db.get(Job, response.json()["id"])
            job.state, job.lease_until, job.lease_token, job.attempts = "running", now() - 1, "lost", 1
        self.assertTrue(run_one(self.db, self.settings))
        with self.db.sessions() as db:
            job = db.get(Job, response.json()["id"])
            self.assertEqual(job.state, "completed")
            self.assertEqual(job.attempts, 2)

    def test_exhausted_lease_becomes_failed(self):
        response = self.post("/tickets/" + self.ticket["id"] + "/analyze")
        with self.db.sessions.begin() as db:
            job = db.get(Job, response.json()["id"])
            job.state, job.lease_until, job.attempts = "running", now() - 1, 3
        run_one(self.db, self.settings)
        with self.db.sessions() as db:
            self.assertEqual(db.get(Job, response.json()["id"]).state, "failed")

    def test_no_second_proposal_after_return_exists(self):
        detail = self.analyzed()
        self.approve(detail["proposal"])
        refreshed = self.analyzed()
        self.assertEqual(refreshed["proposal"]["state"], "approved")
        self.assertIn("уже", refreshed["escalation"])

    def test_csrf_and_origin(self):
        endpoint = self.url("/tickets/" + self.ticket["id"] + "/analyze")
        self.assertEqual(self.client.post(endpoint, json={}).status_code, 403)
        self.assertEqual(self.client.post(endpoint, json={}, headers={
            **self.headers, "origin": "https://attacker.example"}).status_code, 403)

    def test_owner_injection_and_wrong_customer_rejected(self):
        body = {"subject": "New ticket", "customer_name": "Demo", "customer_key": "wrong",
                "message": "Please return my order", "order_reference": "1042"}
        self.assertEqual(self.post("/tickets", body).status_code, 422)
        body["org_id"] = self.other_org
        self.assertEqual(self.post("/tickets", body).status_code, 422)

    def test_logout_revokes_session(self):
        response = self.client.post("/api/auth/logout", json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/session").status_code, 401)

    def test_html_is_preserved_as_text(self):
        response = self.post("/tickets", {"subject": "<b>Example</b>", "customer_name": "<img>",
                                         "customer_key": "new", "message": "<script>alert(1)</script>"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["subject"], "<b>Example</b>")

    def test_oversized_payload(self):
        response = self.client.post(self.url("/tickets"), content="x" * 70000, headers=self.headers)
        self.assertEqual(response.status_code, 413)

    def test_ready(self):
        self.assertEqual(self.client.get("/health/ready").status_code, 200)


if __name__ == "__main__":
    unittest.main()
