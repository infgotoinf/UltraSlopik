# Тест план версии 0.1.1

Среда: локальный demo, Python 3.12.14 и 3.15.0rc2, Chrome; дата 29.10.2026.
Критерий: успешные проверки, нет необработанных 500 и утечки чужих записей.

| ID | Проверка | Ожидание | Инструмент | Итог |
|---|---|---|---|---|
| TC01 | Вход и повторное открытие UI | Сессия восстановлена | Chrome/HTTP | passed |
| TC02 | Создание заявки | 201, owner текущий, status new | UI+unittest | passed |
| TC03 | Пустая тема и границы 3/120/121 | Валидные создаются, остальные 400 | unittest | passed |
| TC04 | Смена статуса admin | new→work→done; 409 для new→done | UI/API | passed |
| TC05 | Пользователь меняет статус | 403, данные не меняются | unittest | passed |
| TC06 | Чужой ID, список и CSV | 403 для ID, чужие строки не выдаются | HTTP/unittest | passed |
| TC07 | Некорректный JSON/тип/CSRF/Origin | 400/415/403 без 500 | unittest | passed |
| TC08 | Фильтр и экспорт CSV | Только нужный статус, безопасные ячейки | UI/unittest | passed |
| TC09 | Backup/restore | Совпадают записи, вход после восстановления | sqlite3 | passed |
| TC10 | Перезапуск и clean release | Состояние сохранено, health 200 | PYZ smoke | passed |
| TC11 | Console, Network, мобильный UI | Нет JS exception; ответы 200; 390px работает | Playwright/CDP | passed |
| TC12 | Скорость и логи | 100 запросов без ошибок, p95<1000ms, без traceback | HTTP timer/logs | passed |

Команды: python tools.py check; python tools.py performance.
Всего 20 автоматических тестов бизнес-логики; отдельный live API-сценарий — 18 запросов.
Сравнение текстов интерфейса и снимков исходников не используется как тест бизнес-логики.
