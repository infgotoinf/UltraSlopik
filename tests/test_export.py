"""Регрессия задачи 001: состав экспорта и права, без проверки надписей UI."""

import csv
import io
import tempfile
import unittest
from pathlib import Path

from helpdesk import core
from helpdesk.export import export_tickets


class ExportTests(unittest.TestCase):
    def test_export_uses_owner_scope_and_status_filter(self):
        Path(".runtime/tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=".runtime/tests") as directory:
            db = Path(directory) / "export.db"
            core.initialize(db)
            core.seed_demo(db)
            student = {"id": 1, "role": "user"}
            admin = {"id": 3, "role": "admin"}
            own = list(
                csv.reader(io.StringIO(export_tickets(db, student).decode("utf-8-sig")), delimiter=";")
            )[1:]
            all_rows = list(
                csv.reader(io.StringIO(export_tickets(db, admin).decode("utf-8-sig")), delimiter=";")
            )[1:]
            filtered = list(
                csv.reader(io.StringIO(export_tickets(db, student, "new").decode("utf-8-sig")), delimiter=";")
            )[1:]
            self.assertEqual({int(row[0]) for row in own}, {1, 2})
            self.assertEqual({int(row[0]) for row in all_rows}, {1, 2, 3})
            self.assertEqual({int(row[0]) for row in filtered}, {1})

    def test_csv_preserves_fields_and_neutralizes_formula_input(self):
        Path(".runtime/tests").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=".runtime/tests") as directory:
            db = Path(directory) / "csv.db"
            core.initialize(db)
            core.seed_demo(db)
            student = {"id": 1, "role": "user"}
            ticket = core.create_ticket(
                db, student, {"title": "=1+1", "description": 'Строка; с разделителем\nи "кавычками"'}
            )
            rows = list(
                csv.reader(io.StringIO(export_tickets(db, student).decode("utf-8-sig")), delimiter=";")
            )[1:]
            row = next(row for row in rows if int(row[0]) == ticket["id"])
            self.assertFalse(row[1].startswith(("=", "+", "-", "@")))
            self.assertEqual(row[2], ticket["description"])
