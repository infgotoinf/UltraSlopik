"""Данные, права и правила работы с заявками. Только стандартная библиотека."""

import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from importlib import resources
from pathlib import Path


class Problem(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript(resources.files("helpdesk").joinpath("schema.sql").read_text())


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return salt + ":" + digest.hex()


def verify_password(password, stored):
    salt = stored.split(":", 1)[0]
    return hmac.compare_digest(hash_password(password, salt), stored)


def create_user(path, username, password, role="user"):
    if role not in {"user", "admin"} or not 3 <= len(username) <= 50 or len(password) < 12:
        raise Problem(400, "Логин от 3 до 50 знаков, пароль от 12 знаков, роль user/admin")
    with connect(path) as db:
        db.execute(
            "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
            (username, hash_password(password), role),
        )


def seed_demo(path):
    """Известные учебные учётные записи. Работает только при явном demo-режиме."""
    with connect(path) as db:
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
    for username, role in [("student", "user"), ("other", "user"), ("admin", "admin")]:
        create_user(path, username, "StudentDemo42!", role)
    with connect(path) as db:
        db.executemany(
            "INSERT INTO tickets(owner_id,title,description,priority,status) VALUES(?,?,?,?,?)",
            [
                (
                    1,
                    "Не работает проектор в аудитории 204",
                    "Изображение пропадает через минуту после включения.",
                    "high",
                    "new",
                ),
                (
                    1,
                    "Нужен доступ к учебной папке",
                    "Прошу открыть доступ к материалам по практике.",
                    "normal",
                    "work",
                ),
                (
                    2,
                    "Обновить браузер в кабинете 312",
                    "Текущая версия не открывает учебный портал.",
                    "low",
                    "done",
                ),
            ],
        )


def login(path, username, password):
    with connect(path) as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        # Одинаковая дорогая проверка и ответ для неизвестного логина и неверного пароля.
        stored = user["password_hash"] if user else "0" * 32 + ":" + "0" * 64
        if not verify_password(password, stored) or not user:
            raise Problem(401, "Неверный логин или пароль")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        db.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, time.time() + 3600),
        )
        return token, {"id": user["id"], "username": user["username"], "role": user["role"], "csrf": csrf}


def session(path, token):
    with connect(path) as db:
        row = db.execute(
            "SELECT u.id,u.username,u.role,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
        if not row:
            raise Problem(401, "Войдите в систему")
        return dict(row)


def logout(path, token):
    with connect(path) as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def list_tickets(path, user, status=""):
    if status and status not in {"new", "work", "done"}:
        raise Problem(400, "Неизвестный статус")
    query = "SELECT t.*,u.username AS owner FROM tickets t JOIN users u ON u.id=t.owner_id WHERE 1=1"
    args = []
    if user["role"] != "admin":
        query += " AND t.owner_id=?"
        args.append(user["id"])
    if status:
        query += " AND t.status=?"
        args.append(status)
    with connect(path) as db:
        return [dict(row) for row in db.execute(query + " ORDER BY t.id DESC", args)]


def get_ticket(path, user, ticket_id):
    with connect(path) as db:
        row = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        raise Problem(404, "Заявка не найдена")
    if user["role"] != "admin" and row["owner_id"] != user["id"]:
        raise Problem(403, "Нет доступа к чужой заявке")
    return dict(row)


def create_ticket(path, user, data):
    title = data.get("title", "")
    description = data.get("description", "")
    priority = data.get("priority", "normal")
    if not isinstance(title, str) or not 3 <= len(title.strip()) <= 120:
        raise Problem(400, "Тема должна содержать от 3 до 120 знаков")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 2000:
        raise Problem(400, "Описание должно содержать от 1 до 2000 знаков")
    if priority not in ("low", "normal", "high"):
        raise Problem(400, "Неизвестный приоритет")
    with connect(path) as db:
        cursor = db.execute(
            "INSERT INTO tickets(owner_id,title,description,priority) VALUES(?,?,?,?)",
            (user["id"], title.strip(), description.strip(), priority),
        )
        ticket_id = cursor.lastrowid
        db.execute(
            "INSERT INTO audit(user_id,action,ticket_id) VALUES(?,?,?)", (user["id"], "create", ticket_id)
        )
    return get_ticket(path, user, ticket_id)


def change_status(path, user, ticket_id, status):
    if user["role"] != "admin":
        raise Problem(403, "Статус меняет только сотрудник поддержки")
    if status not in ("new", "work", "done"):
        raise Problem(400, "Неизвестный статус")
    with connect(path) as db:
        row = db.execute("SELECT status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row:
            raise Problem(404, "Заявка не найдена")
        allowed = {"new": {"work"}, "work": {"new", "done"}, "done": {"work"}}
        if status not in allowed[row["status"]]:
            raise Problem(409, "Недопустимый переход статуса")
        db.execute(
            "UPDATE tickets SET status=?,updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (status, ticket_id),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,ticket_id) VALUES(?,?,?)",
            (user["id"], "status:" + status, ticket_id),
        )
    return get_ticket(path, user, ticket_id)


def backup(source, destination):
    target = Path(destination)
    if Path(source).resolve() == target.resolve():
        raise Problem(400, "Копия должна отличаться от рабочей БД")
    target.parent.mkdir(parents=True, exist_ok=True)
    with connect(source) as src, connect(target) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise Problem(500, "Резервная копия повреждена")


def restore(source, destination):
    if not Path(source).is_file():
        raise Problem(400, "Файл резервной копии не найден")
    with connect(source) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise Problem(400, "Некорректная резервная копия")
        required = {"users", "tickets", "audit", "sessions"}
        actual = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= actual:
            raise Problem(400, "Это не резервная копия ServiceDesk")
    backup(source, destination)
    with connect(destination) as db:
        db.execute("DELETE FROM sessions")
