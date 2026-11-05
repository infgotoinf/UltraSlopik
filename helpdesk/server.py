"""Локальное учебное приложение. Не предназначено для публичного production."""

import argparse
import getpass
import json
import logging
import os
import sqlite3
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from helpdesk import __version__, core
from helpdesk.export import export_tickets

LOG = logging.getLogger("helpdesk")


def load_config():
    settings = {}
    env_file = Path(os.environ.get("ENV_FILE", ".env"))
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip()
    settings.update(
        {
            k: v
            for k, v in os.environ.items()
            if k.startswith("APP_") or k in {"DB_PATH", "DEMO_SEED", "ALLOWED_HOSTS"}
        }
    )
    config = {
        "host": settings.get("APP_HOST", "127.0.0.1"),
        "port": int(settings.get("APP_PORT", "8080")),
        "db": settings.get("DB_PATH", "data/helpdesk.db"),
        "demo": settings.get("DEMO_SEED", "true").lower() == "true",
        "env": settings.get("APP_ENV", "demo"),
        "hosts": settings.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(","),
    }
    if config["env"] == "production":
        raise ValueError("Для публичного production нужен промышленный сервер и HTTPS. Используйте demo.")
    return config


def make_server(db_path, host="127.0.0.1", port=8080, hosts=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ServiceDesk"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, fmt, *args):
            # Не логируем Cookie, пароли, тело запросов и query string.
            LOG.info(
                "http method=%s path=%s status=%s",
                self.command,
                urlsplit(self.path).path,
                args[1] if len(args) > 1 else "-",
            )

        def reply(self, status, data, content_type="application/json; charset=utf-8", extra=None):
            body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def token(self):
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            return cookies["sid"].value if "sid" in cookies else ""

        def user(self, csrf=False):
            user = core.session(db_path, self.token())
            if csrf and self.headers.get("X-CSRF-Token", "") != user["csrf"]:
                raise core.Problem(403, "Не пройдена проверка запроса")
            return user

        def body(self):
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise core.Problem(415, "Нужен формат application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise core.Problem(400, "Некорректный размер запроса") from None
            if not 0 < length <= 16_384:
                raise core.Problem(413, "Размер запроса должен быть от 1 до 16384 байт")
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise core.Problem(400, "Некорректный JSON") from None
            if not isinstance(data, dict):
                raise core.Problem(400, "Ожидается объект JSON")
            return data

        def dispatch(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            request_host = self.headers.get("Host", "")
            if urlsplit("//" + request_host).hostname not in (hosts or ["127.0.0.1", "localhost"]):
                raise core.Problem(400, "Недопустимый Host")
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + request_host:
                raise core.Problem(403, "Запрос с другого сайта запрещен")
            if self.command == "GET":
                assets = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/style.css": ("style.css", "text/css; charset=utf-8"),
                    "/favicon.ico": (None, None),
                }
                if path in assets:
                    name, mime = assets[path]
                    return (
                        self.reply(
                            200, resources.files("helpdesk").joinpath("static", name).read_bytes(), mime
                        )
                        if name
                        else self.reply(204, b"")
                    )
                if path == "/api/health":
                    with core.connect(db_path) as db:
                        db.execute("SELECT 1 FROM tickets LIMIT 1")
                    return self.reply(200, {"status": "ok", "version": __version__, "pid": os.getpid()})
                if path == "/api/me":
                    try:
                        user = self.user()
                    except core.Problem as error:
                        if error.status != 401:
                            raise
                        user = {"authenticated": False}
                    return self.reply(200, user)
                if path == "/api/export":
                    user = self.user()
                    status = parse_qs(parsed.query).get("status", [""])[0]
                    return self.reply(
                        200,
                        export_tickets(db_path, user, status),
                        "text/csv; charset=utf-8",
                        {"Content-Disposition": 'attachment; filename="tickets.csv"'},
                    )
                if path == "/api/tickets":
                    status = parse_qs(parsed.query).get("status", [""])[0]
                    return self.reply(200, core.list_tickets(db_path, self.user(), status))
                if path.startswith("/api/tickets/") and path[13:].isdigit():
                    return self.reply(200, core.get_ticket(db_path, self.user(), int(path[13:])))
                if path == "/api/admin/stats":
                    user = self.user()
                    if user["role"] != "admin":
                        raise core.Problem(403, "Только для сотрудника поддержки")
                    with core.connect(db_path) as db:
                        rows = db.execute("SELECT status,COUNT(*) AS count FROM tickets GROUP BY status")
                        return self.reply(200, {r["status"]: r["count"] for r in rows})
            if self.command == "POST":
                if path == "/api/login":
                    now = time.monotonic()
                    attempts = self.server.login_attempts
                    ip = self.client_address[0]
                    attempts[ip] = [t for t in attempts.get(ip, []) if now - t < 60]
                    if len(attempts[ip]) >= 10:
                        raise core.Problem(429, "Слишком много попыток входа. Подождите минуту")
                    data = self.body()
                    username, password = data.get("username", ""), data.get("password", "")
                    if (
                        not isinstance(username, str)
                        or not isinstance(password, str)
                        or len(username) > 50
                        or len(password) > 200
                    ):
                        raise core.Problem(400, "Некорректные данные входа")
                    attempts[ip].append(now)
                    token, user = core.login(db_path, username, password)
                    return self.reply(
                        200,
                        user,
                        extra={"Set-Cookie": f"sid={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600"},
                    )
                if path == "/api/logout":
                    self.user(csrf=True)
                    core.logout(db_path, self.token())
                    return self.reply(
                        200,
                        {"ok": True},
                        extra={"Set-Cookie": "sid=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"},
                    )
                if path == "/api/tickets":
                    user = self.user(csrf=True)
                    return self.reply(201, core.create_ticket(db_path, user, self.body()))
            if self.command == "PATCH" and path.startswith("/api/tickets/") and path[13:].isdigit():
                user = self.user(csrf=True)
                return self.reply(
                    200, core.change_status(db_path, user, int(path[13:]), self.body().get("status"))
                )
            raise core.Problem(404, "Маршрут не найден")

        def handle_request(self):
            try:
                self.dispatch()
            except core.Problem as error:
                self.reply(error.status, {"error": error.message})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except sqlite3.Error:
                LOG.exception("database_error")
                self.reply(503, {"error": "Хранилище временно недоступно"})
            except Exception:
                LOG.exception("request_error")
                self.reply(500, {"error": HTTPStatus(500).phrase})

        do_GET = handle_request
        do_POST = handle_request
        do_PATCH = handle_request
        do_OPTIONS = handle_request

    server = ThreadingHTTPServer((host, port), Handler)
    server.login_attempts = {}
    return server


def main():
    parser = argparse.ArgumentParser(description="ServiceDesk — учёт заявок в техподдержку")
    parser.add_argument(
        "command", nargs="?", default="run", choices=["run", "seed", "user", "backup", "restore"]
    )
    parser.add_argument("--file", default="backups/helpdesk.db")
    parser.add_argument("--username", default="operator")
    parser.add_argument("--role", choices=["user", "admin"], default="user")
    parser.add_argument("--target", default="data/restored.db")
    args = parser.parse_args()
    config = load_config()
    core.initialize(config["db"])
    if args.command == "backup":
        core.backup(config["db"], args.file)
        print("Backup OK:", args.file)
        return
    if args.command == "restore":
        if Path(args.target).resolve() == Path(config["db"]).resolve():
            raise ValueError("Сначала восстановите в отдельную БД и проверьте данные")
        core.restore(args.file, args.target)
        print("Restore OK:", args.target)
        return
    if args.command == "user":
        core.create_user(config["db"], args.username, getpass.getpass("Пароль (от 12 знаков): "), args.role)
        print("Пользователь создан")
        return
    if config["demo"]:
        core.seed_demo(config["db"])
    if args.command == "seed":
        print("Demo database ready:", config["db"])
        return
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("logs/app.log", encoding="utf-8")],
    )
    with make_server(config["db"], config["host"], config["port"], config["hosts"]) as server:
        LOG.info(
            "ServiceDesk %s ready at http://%s:%s env=%s",
            __version__,
            config["host"],
            config["port"],
            config["env"],
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOG.info("Shutdown requested")


if __name__ == "__main__":
    main()
