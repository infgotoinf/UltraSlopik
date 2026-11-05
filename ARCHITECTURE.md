# Архитектура

```mermaid
flowchart LR
    U[Браузер студента или сотрудника] -->|HTTP JSON и Cookie| A[server.py]
    A --> C[core.py права и заявки]
    A --> E[export.py CSV]
    E --> C
    C --> D[(SQLite)]
    T[tools.py и BAT Makefile] --> A
    T --> B[Backup и release ZIP]
```

ER: users 1—N tickets; users 1—N sessions; users 1—N audit; tickets 1—N audit.
Владельца заявке назначает сервер из сессии, не клиент. Смена статуса и запись
audit находятся в одной транзакции. Frontend использует textContent для пользовательских полей.
В schema.sql стоит user_version=1, повторный запуск создаёт только недостающие таблицы.
