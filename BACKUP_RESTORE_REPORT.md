# Проверка резервного копирования

Источник: data/helpdesk.db. Копия: backups/helpdesk.db (32768 байт).
Восстановлено в отдельный data/restored.db, рабочий файл не перезаписывался.
Метод: sqlite3.Connection.backup, затем integrity_check и сравнение всех строк.

users: 3 строк; tickets: 5 строк;
audit: 4 строки. До/после полностью совпадают.
Integrity: ok. Сессии после restore удалены, повторный вход student успешен,
видны 4 собственные заявки. Копия и JSON приложены в этапе 5.

Команды: python tools.py backup; python tools.py restore.
CLI с параметрами: python run.py backup --file backups/manual.db;
python run.py restore --file backups/manual.db --target data/recovered.db.
Для переключения: остановить приложение, задать DB_PATH=data/recovered.db в .env,
запустить снова и пройти основной сценарий. CLI запрещает restore прямо в активный DB_PATH.

Периодичность: перед обновлением и раз в учебный день. Хранение: 7 копий,
одна на отдельном носителе. Сейчас автоматического расписания и внешнего хранения нет.
Цель учебного восстановления: потерять не более дня данных, восстановить за 15 минут;
это целевые значения, промышленный SLA не измерялся.
