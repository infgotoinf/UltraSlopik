# Проверка безопасности

Проверяется локальный учебный стенд с синтетическими данными.

| Проверка | Результат и доказательство |
|---|---|
| .env/БД/backup не в Git | git ls-files и .gitignore, security_scan.txt |
| Пример настроек без реальных секретов | .env.example; случайных токенов в исходниках нет; demo-пароль явно публичный |
| Поиск подозрительных значений | Ручной просмотр core/server, git grep; совпадения — имена полей и примеры |
| Зависимости | OSV Ruff 0.14.3: 0 известных записей на дату проверки; runtime pip-пакетов 0 |
| Роли | student→admin/stats =403; admin→admin/stats =200, api_results.json |
| Чужие данные | student→ticket/3 =403; own list/CSV без owner 2 |
| CORS/Host/CSRF | Cross-Origin запрещён 403, чужой Host 400; allow-origin * не выдается |
| Ошибки и debug | Подробный traceback не возвращается; APP_DEBUG=false в demo |
| Backup | backups/helpdesk.db создан SQLite backup API, 32768 байт |
| Restore | users/tickets/audit совпадают, integrity ok, повторный вход успешен |
| Порты | 127.0.0.1:8080 LISTENING; отдельного порта SQLite нет, ports.txt |
| Логи | Проверены после сценариев; ожидаемые 400/401/403/404/409 объяснены; необработанных 500 нет |

Повторить: python tools.py security-check; python tools.py deps-check;
python tools.py backup; python tools.py restore; python tools.py ports-check.
Не используется формулировка «полностью защищено». Остаточные риски в RISK_REGISTER.md.
