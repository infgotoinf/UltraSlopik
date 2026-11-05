FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 student && mkdir -p /app/data /app/logs && chown -R student:student /app
COPY --chown=student:student helpdesk ./helpdesk
COPY --chown=student:student run.py .
USER student
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_HOST=0.0.0.0 APP_ENV=demo
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)" || exit 1
CMD ["python", "run.py"]
