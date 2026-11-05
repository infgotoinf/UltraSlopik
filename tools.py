"""Единые переносимые команды проекта. Python 3.12+, без PowerShell."""

import argparse
import importlib.metadata
import json
import os
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipapp
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
RUNTIME = ROOT / ".runtime"
RUNTIME.mkdir(exist_ok=True)
os.environ.update(
    {
        "PIP_CACHE_DIR": str(RUNTIME / "pip-cache"),
        "TMP": str(RUNTIME),
        "TEMP": str(RUNTIME),
        "TMPDIR": str(RUNTIME),
    }
)
tempfile.tempdir = str(RUNTIME)
sys.path.insert(0, str(ROOT / ".tools"))


def execute(*args):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def ruff(*args):
    execute(sys.executable, ROOT / ".tools/ruff/__main__.py", *args)


def setup():
    execute(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--target",
        ".tools",
        "--upgrade",
        "-r",
        "requirements-dev.txt",
    )
    if not Path(".env").exists():
        shutil.copyfile(".env.example", ".env")
    execute(sys.executable, "run.py", "seed")


def test():
    execute(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")


def check():
    ruff("check", "helpdesk", "tests", "tools.py", "run.py")
    ruff("format", "--check", "helpdesk", "tests", "tools.py", "run.py")
    test()


def build():
    from helpdesk import __version__

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNTIME) as temporary:
        temporary = Path(temporary)
        shutil.copytree(
            ROOT / "helpdesk", temporary / "helpdesk", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        pyz = dist / "servicedesk.pyz"
        zipapp.create_archive(
            temporary, pyz, main="helpdesk.server:main", interpreter="/usr/bin/env python3", compressed=True
        )
    archive = dist / f"ServiceDesk-{__version__}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        output.write(pyz, pyz.name)
        for name in [".env.demo.example", "DEMO_GUIDE.md", "RELEASE_NOTES.md"]:
            if Path(name).exists():
                output.write(name, name)
        output.writestr("start.bat", '@echo off\r\ncd /d "%~dp0"\r\npython servicedesk.pyz\r\npause\r\n')
        output.writestr("start.sh", '#!/bin/sh\ncd "$(dirname "$0")"\nexec python3 servicedesk.pyz\n')
        output.writestr(
            "demo_readme.txt",
            "ServiceDesk. Python 3.12+. Run: python servicedesk.pyz\nOpen http://127.0.0.1:8080\nDemo users: student / other / admin; password: StudentDemo42!\nLocal teaching demo only. Stop with Ctrl+C. Data: data/helpdesk.db\n",
        )
    print("BUILD OK", archive, archive.stat().st_size, "bytes")


def health(url=None):
    from helpdesk.server import load_config

    port = load_config()["port"]
    with urllib.request.urlopen(url or f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
        return json.load(response)


def deploy():
    from helpdesk.server import load_config

    if (RUNTIME / "process.json").exists():
        raise RuntimeError("Есть запись о процессе. Сначала выполните stop или restart")
    config = load_config()
    with socket.socket() as probe:
        probe.bind((config["host"], config["port"]))
    log = ROOT / "logs/deploy.log"
    log.parent.mkdir(exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log.open("ab") as output:
        process = subprocess.Popen(
            [sys.executable, "run.py"], stdout=output, stderr=output, creationflags=flags
        )
    record = {"pid": process.pid, "port": config["port"]}
    for _ in range(50):
        if process.poll() is not None:
            raise RuntimeError(log.read_text(encoding="utf-8"))
        try:
            result = health()
            if result.get("pid") == process.pid:
                (RUNTIME / "process.json").write_text(json.dumps(record))
                print("DEPLOY OK", json.dumps(result), f"http://127.0.0.1:{config['port']}")
                return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    process.terminate()
    raise RuntimeError("Сервис не запустился за 5 секунд")


def stop():
    record_path = RUNTIME / "process.json"
    if not record_path.exists():
        print("Нет управляемого процесса")
        return
    record = json.loads(record_path.read_text())
    try:
        result = health(f"http://127.0.0.1:{record['port']}/api/health")
    except (OSError, urllib.error.URLError):
        record_path.unlink()
        print("Процесс уже остановлен")
        return
    if result.get("pid") != record["pid"]:
        raise RuntimeError("PID сервиса отличается. Остановка отменена")
    os.kill(record["pid"], signal.SIGTERM)
    record_path.unlink()
    for _ in range(30):
        try:
            health(f"http://127.0.0.1:{record['port']}/api/health")
        except (OSError, urllib.error.URLError):
            print("STOP OK", record["pid"])
            return
        time.sleep(0.1)
    raise RuntimeError("Порт всё ещё отвечает")


def restart():
    stop()
    deploy()


def logs():
    path = ROOT / "logs/app.log"
    print(
        "\n".join(path.read_text(encoding="utf-8").splitlines()[-50:])
        if path.exists()
        else "Лог ещё не создан"
    )


def performance():
    from helpdesk import core
    from helpdesk.server import make_server

    with tempfile.TemporaryDirectory(dir=RUNTIME) as directory:
        db = Path(directory) / "load.db"
        core.initialize(db)
        core.seed_demo(db)
        token, _ = core.login(db, "student", "StudentDemo42!")
        with make_server(db, port=0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            samples = []
            for _ in range(100):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/tickets", headers={"Cookie": "sid=" + token}
                )
                started = time.perf_counter()
                with urllib.request.urlopen(request, timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError("Ошибка нагрузочной проверки")
                    json.load(response)
                samples.append((time.perf_counter() - started) * 1000)
            server.shutdown()
            thread.join()
    result = {
        "endpoint": "GET /api/tickets",
        "requests": len(samples),
        "concurrency": 1,
        "errors": 0,
        "mean_ms": round(statistics.mean(samples), 2),
        "p95_ms": round(sorted(samples)[94], 2),
        "max_ms": round(max(samples), 2),
        "scope": "local synthetic DB; not an Internet capacity estimate",
    }
    (RUNTIME / "performance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def deps_check():
    # OSV проверяет фиксированную dev-зависимость. Рабочих pip-зависимостей нет.
    version = importlib.metadata.version("ruff")
    request = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=json.dumps({"package": {"name": "ruff", "ecosystem": "PyPI"}, "version": version}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    summary = {
        "runtime_dependencies": 0,
        "dev_package": "ruff",
        "version": version,
        "osv_ids": [v["id"] for v in result.get("vulns", [])],
        "scope": "OSV package query; CPython/OS not covered",
    }
    (RUNTIME / "dependencies.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if summary["osv_ids"]:
        raise RuntimeError("Есть известные уязвимости dev-зависимости")


def security_check():
    test()
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    forbidden = [
        p
        for p in result.stdout.splitlines()
        if p in {".env", ".env.demo", ".env.production"}
        or p.endswith((".db", ".pem", ".key"))
        or p.startswith(("backups/", "data/", "logs/"))
    ]
    print("Tracked secret/data files:", forbidden)
    if forbidden:
        raise RuntimeError("В Git обнаружены приватные файлы")
    print("SECURITY CHECK OK. Review residual risks in RISK_REGISTER.md")


def ports_check():
    from helpdesk.server import load_config

    config = load_config()
    print("Configured bind:", config["host"], config["port"])
    print("Health:", health())
    if os.name == "nt":
        result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
    else:
        result = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, check=True)
    print("\n".join(line for line in result.stdout.splitlines() if f":{config['port']}" in line))


def main():
    commands = {
        "setup": setup,
        "run": lambda: execute(sys.executable, "run.py"),
        "check": check,
        "test": test,
        "api-test": test,
        "format": lambda: ruff("format", "helpdesk", "tests", "tools.py", "run.py"),
        "build": build,
        "build-release": build,
        "deploy": deploy,
        "restart": restart,
        "stop": stop,
        "check-deploy": lambda: print(json.dumps(health(), indent=2)),
        "logs": logs,
        "logs-check": logs,
        "logs-security": logs,
        "performance": performance,
        "deps-check": deps_check,
        "security-check": security_check,
        "ports-check": ports_check,
        "backup": lambda: execute(sys.executable, "run.py", "backup"),
        "restore": lambda: execute(sys.executable, "run.py", "restore"),
        "docker-up": lambda: execute("docker", "compose", "up", "--build", "-d"),
        "docker-down": lambda: execute("docker", "compose", "down"),
        "quality-check": lambda: (check(), performance()),
        "release-check": lambda: (check(), build()),
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=commands)
    args = parser.parse_args()
    commands[args.command]()


if __name__ == "__main__":
    main()
