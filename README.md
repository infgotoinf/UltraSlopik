# ServiceDesk

Учёт заявок в техподдержку учебного корпуса. Автор: Манько Аким, УП.03, 2026.

Пользователь создаёт и просматривает свои заявки. Сотрудник поддержки видит все заявки
и переводит их по статусам «Новая → В работе → Решена». Есть фильтр, журнал действий,
резервное копирование SQLite и переносимая сборка.

## Быстрый запуск

Нужен Python 3.12 или новее с модулем sqlite3. Внешних библиотек для запуска нет.

```sh
python run.py
```

Открыть http://127.0.0.1:8080. Учебные логины: `student`, `other`, `admin`.
Общий **публичный демонстрационный** пароль: `StudentDemo42!`.
Выйти из сервера: Ctrl+C. Для обычной учебной демонстрации установка Ruff не нужна.

## Проверки и сборка

```sh
python tools.py setup
python tools.py check
python tools.py build
python tools.py performance
```

Windows: `scripts\setup.bat`, `scripts\run.bat`, `scripts\check.bat`.
Linux/macOS: `make setup`, `make run`, `make check` (или те же команды Python).
Все BAT переходят в корень проекта и возвращают код ошибки. PowerShell не требуется.

## Состав

- `helpdesk/core.py` — SQLite, авторизация, права, заявки, backup/restore.
- `helpdesk/server.py` — локальный HTTP API, конфигурация и CLI.
- `helpdesk/static/` — интерфейс без сборщика и сетевых CDN.
- `helpdesk/schema.sql` — идемпотентная миграция версии 1.
- `tests/test_business.py` — бизнес-сценарии через сервис и HTTP.
- `tools.py`, `scripts/`, `Makefile` — установка, качество, сборка, эксплуатация.
- `.github/workflows/ci.yml` — CI для push/PR после публикации в GitHub.

Основные документы: INSTALL.md, CONFIGURATION.md, DEPLOYMENT.md, TEST_PLAN.md,
SECURITY_CHECKLIST.md, INCIDENT_REPORT.md, RELEASE_NOTES.md. API описан в API.md.

## Хранение и область применения

Данные создаются в `data/helpdesk.db`, логи в `logs/`, копии в `backups/`.
Они исключены из Git и релизной сборки. Переменные из `.env` переопределяются окружением.
Секретного ключа в этой схеме нет: сессии случайные, их хеши и срок действия хранятся в БД.
Не добавляйте вымышленные SECRET_KEY/SMTP, которые приложение не читает.

Это локальная учебная система с браузерным интерфейсом. Встроенный HTTP-сервер,
учебные аккаунты и HTTP рассчитаны на loopback. Публичный production запрещён
проверкой APP_ENV. Для него нужны отдельный промышленный сервер, HTTPS и аудит.

Репозиторий находится в этой папке. Переносимая история приложена как Git bundle.
Публикация в GitHub не выполнялась; готовый workflow не является удалённым CI run.
