"""Права, жизненный цикл заявок, сохранение и восстановление данных."""

import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

from helpdesk import core
from helpdesk.server import make_server


class ServiceDeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = Path(".runtime/tests")
        cls.runtime.mkdir(parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=cls.runtime)
        cls.db = str(Path(cls.temp.name) / "test.db")
        core.initialize(cls.db)
        core.seed_demo(cls.db)
        cls.student = {"id": 1, "username": "student", "role": "user"}
        cls.other = {"id": 2, "username": "other", "role": "user"}
        cls.admin = {"id": 3, "username": "admin", "role": "admin"}
        cls.server = make_server(cls.db, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, method, path, data=None, cookie=None, csrf=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        request_headers = {"Content-Type": "application/json"}
        if cookie:
            request_headers["Cookie"] = cookie
        if csrf:
            request_headers["X-CSRF-Token"] = csrf
        request_headers.update(headers or {})
        connection.request(method, path, json.dumps(data) if data is not None else None, request_headers)
        response = connection.getresponse()
        status, response_headers, raw = response.status, dict(response.getheaders()), response.read()
        connection.close()
        payload = (
            json.loads(raw) if raw and "application/json" in response_headers.get("Content-Type", "") else raw
        )
        return status, response_headers, payload

    def credentials(self, username="student"):
        status, headers, data = self.request(
            "POST", "/api/login", {"username": username, "password": "StudentDemo42!"}
        )
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";")[0], data["csrf"]

    def new_ticket(self, title="Проверка печати"):
        return core.create_ticket(
            self.db, self.student, {"title": title, "description": "Принтер не печатает"}
        )

    def test_create_assigns_owner_and_new_status(self):
        result = self.new_ticket()
        self.assertEqual(result["owner_id"], self.student["id"])
        self.assertEqual(result["status"], "new")
        with core.connect(self.db) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM audit WHERE ticket_id=?", (result["id"],)).fetchone()[0], 1
            )

    def test_title_validation_boundaries(self):
        for title in ["", "  ", "ab", "x" * 121, None, [1]]:
            with self.subTest(length=len(title) if isinstance(title, str) else None):
                with self.assertRaises(core.Problem) as error:
                    self.new_ticket(title)
                self.assertEqual(error.exception.status, 400)
        self.assertGreater(self.new_ticket("abc")["id"], 0)
        self.assertGreater(self.new_ticket("x" * 120)["id"], 0)

    def test_description_and_priority_validation(self):
        for data in [
            {"description": ""},
            {"description": "x" * 2001},
            {"priority": "urgent"},
            {"priority": [1]},
        ]:
            with self.assertRaises(core.Problem) as error:
                core.create_ticket(
                    self.db, self.student, {"title": "Новая заявка", "description": "Тест", **data}
                )
            self.assertEqual(error.exception.status, 400)

    def test_owner_only_reads_own_tickets(self):
        ticket = self.new_ticket()
        rows = core.list_tickets(self.db, self.other)
        self.assertNotIn(ticket["id"], [r["id"] for r in rows])
        with self.assertRaises(core.Problem) as error:
            core.get_ticket(self.db, self.other, ticket["id"])
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(core.get_ticket(self.db, self.admin, ticket["id"])["id"], ticket["id"])

    def test_admin_status_lifecycle(self):
        ticket = self.new_ticket()
        for status in ["work", "done", "work", "new"]:
            result = core.change_status(self.db, self.admin, ticket["id"], status)
            self.assertEqual(result["status"], status)

    def test_user_cannot_change_status(self):
        ticket = self.new_ticket()
        with self.assertRaises(core.Problem) as error:
            core.change_status(self.db, self.student, ticket["id"], "work")
        self.assertEqual(error.exception.status, 403)
        self.assertEqual(core.get_ticket(self.db, self.admin, ticket["id"])["status"], "new")

    def test_invalid_transition_does_not_mutate_data(self):
        ticket = self.new_ticket()
        with self.assertRaises(core.Problem) as error:
            core.change_status(self.db, self.admin, ticket["id"], "done")
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(core.get_ticket(self.db, self.admin, ticket["id"])["status"], "new")

    def test_filter_returns_only_matching_rows(self):
        ticket = self.new_ticket()
        core.change_status(self.db, self.admin, ticket["id"], "work")
        rows = core.list_tickets(self.db, self.student, "work")
        self.assertIn(ticket["id"], [r["id"] for r in rows])
        self.assertTrue(all(r["status"] == "work" and r["owner_id"] == 1 for r in rows))

    def test_unknown_resource_is_404(self):
        with self.assertRaises(core.Problem) as error:
            core.get_ticket(self.db, self.admin, 999999)
        self.assertEqual(error.exception.status, 404)

    def test_login_invalid_and_sql_injection(self):
        for username, password in [("student", "bad"), ("' OR 1=1 --", "any")]:
            with self.assertRaises(core.Problem) as error:
                core.login(self.db, username, password)
            self.assertEqual(error.exception.status, 401)

    def test_sessions_expire_and_logout_revokes(self):
        token, user = core.login(self.db, "student", "StudentDemo42!")
        self.assertEqual(core.session(self.db, token)["id"], user["id"])
        core.logout(self.db, token)
        with self.assertRaises(core.Problem):
            core.session(self.db, token)
        token, _ = core.login(self.db, "student", "StudentDemo42!")
        with core.connect(self.db) as db:
            db.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
        with self.assertRaises(core.Problem):
            core.session(self.db, token)

    def test_backup_restore_preserves_records_and_revokes_sessions(self):
        ticket = self.new_ticket()
        backup = Path(self.temp.name) / "backup.db"
        target = Path(self.temp.name) / "restored.db"
        core.login(self.db, "student", "StudentDemo42!")
        core.backup(self.db, backup)
        with core.connect(self.db) as db:
            original = [tuple(r) for r in db.execute("SELECT * FROM tickets ORDER BY id")]
        core.restore(backup, target)
        with core.connect(target) as db:
            self.assertEqual(original, [tuple(r) for r in db.execute("SELECT * FROM tickets ORDER BY id")])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
        self.assertEqual(core.get_ticket(target, self.student, ticket["id"])["owner_id"], 1)

    def test_health_and_anonymous_denied(self):
        self.assertEqual(self.request("GET", "/api/health")[0], 200)
        self.assertEqual(self.request("GET", "/api/tickets")[0], 401)

    def test_http_create_and_missing_csrf(self):
        cookie, csrf = self.credentials()
        data = {"title": "HTTP заявка", "description": "Из API"}
        self.assertEqual(self.request("POST", "/api/tickets", data, cookie)[0], 403)
        status, _, result = self.request("POST", "/api/tickets", data, cookie, csrf)
        self.assertEqual(status, 201)
        self.assertEqual(result["owner_id"], 1)
        self.assertEqual(
            self.request("GET", f"/api/tickets/{result['id']}", cookie=cookie)[2]["id"], result["id"]
        )

    def test_admin_api_denied_to_user(self):
        cookie, _ = self.credentials()
        self.assertEqual(self.request("GET", "/api/admin/stats", cookie=cookie)[0], 403)

    def test_export_http_requires_session_and_preserves_scope(self):
        import csv
        import io

        self.assertEqual(self.request("GET", "/api/export")[0], 401)
        cookie, _ = self.credentials()
        status, _, raw = self.request("GET", "/api/export", cookie=cookie)
        self.assertEqual(status, 200)
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))[1:]
        expected = {r["id"] for r in core.list_tickets(self.db, self.student)}
        self.assertEqual({int(row[0]) for row in rows}, expected)

    def test_invalid_host_and_origin_denied(self):
        self.assertEqual(self.request("GET", "/api/health", headers={"Host": "evil.example"})[0], 400)
        self.assertEqual(
            self.request("POST", "/api/login", {}, headers={"Origin": "https://evil.example"})[0], 403
        )

    def test_json_errors_are_handled(self):
        self.assertEqual(self.request("POST", "/api/login", [1, 2])[0], 400)
        self.assertEqual(
            self.request("POST", "/api/login", {}, headers={"Content-Type": "text/plain"})[0], 415
        )
