"""CSV-выгрузка с теми же правами, что у списка заявок."""

import csv
import io

from helpdesk.core import list_tickets


def safe_cell(value):
    text = str(value)
    # Защита от формул в табличных редакторах, включая ведущие пробелы.
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n"))
        else text
    )


def export_tickets(path, user, status=""):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Тема", "Описание", "Приоритет", "Статус", "Автор", "Создана"])
    for row in list_tickets(path, user, status):
        writer.writerow(
            [
                safe_cell(row[key])
                for key in ["id", "title", "description", "priority", "status", "owner", "created_at"]
            ]
        )
    return output.getvalue().encode("utf-8-sig")
