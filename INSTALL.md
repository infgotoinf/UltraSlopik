# Установка и запуск

1. Установить Python 3.12+ с sqlite3. Распаковать проект в доступную для записи папку.
2. Открыть терминал в project. Выполнить `python run.py`.
3. Открыть http://127.0.0.1:8080. Войти как student с паролем StudentDemo42!.
4. Создать заявку. Проверить её в списке. Остановить сервер Ctrl+C.

Проверки для разработчика: `python tools.py setup`, затем `python tools.py check`.
setup устанавливает только Ruff 0.14.3 в .tools, создаёт .env и учебную БД.
Интернет нужен для первой установки Ruff, но не для запуска программы.
Windows: scripts\setup.bat, scripts\run.bat, scripts\check.bat, scripts\format.bat.
Linux/macOS: python3 вместо python; Makefile использует python3 по умолчанию.

Docker: `docker compose up --build -d`, адрес тот же; остановка `docker compose down`.
В Compose один сервис app, так как SQLite встроена, db-контейнер был бы лишним.
Контейнер работает от uid 10001. Для Linux bind-mount папкам data/logs нужны права
этого пользователя. Docker-конфиги проверены командой compose config; сборка
образа не выполнялась, чтобы все изменения остались в папке задания.

При занятом 8080 сменить APP_PORT в .env; в Docker также сменить левую часть ports.
При ModuleNotFoundError запускать из корня project. При отсутствии pip runtime
всё равно работает; pip нужен только для setup. Не копировать .env, data и .tools в Git.
