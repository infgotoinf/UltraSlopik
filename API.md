# API

JSON, UTF-8. Авторизация через HttpOnly cookie sid. POST/PATCH требуют CSRF-токен
из ответа входа в X-CSRF-Token. GET не изменяет данные. Ошибки имеют JSON-поле error.

| Метод | Маршрут | Действие / коды |
|---|---|---|
| GET | /api/health | БД доступна, версия, PID; 200/503 |
| GET | /api/me | Текущая сессия или authenticated=false; 200 |
| POST | /api/login | username/password; 200/401/429 |
| POST | /api/logout | Удаление сессии; 200/401/403 |
| GET | /api/tickets?status=new | Свои заявки, admin — все; 200/400/401 |
| GET | /api/tickets/1 | Одна запись; 200/401/403/404 |
| POST | /api/tickets | title, description, priority; 201/400/401/403 |
| PATCH | /api/tickets/1 | status, только admin; 200/400/403/404/409 |
| GET | /api/admin/stats | Счётчики по статусам, только admin; 200/403 |
| GET | /api/export?status=work | CSV UTF-8 BOM, те же права и фильтр; 200/400/401 |

Статусы: new→work; work→new/done; done→work. Прямой new→done запрещён (409).
Тема 3–120 знаков после trim, описание 1–2000, приоритет low/normal/high.
Предел тела HTTP-запроса 16384 байта. HTML в заявках отображается как текст.
