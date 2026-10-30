FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

RUN groupadd --system --gid 10001 gitscope \
    && useradd --system --uid 10001 --gid gitscope --home-dir /app gitscope \
    && chown gitscope:gitscope /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=gitscope:gitscope . .

USER gitscope
EXPOSE 5000
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-60} --graceful-timeout ${GUNICORN_GRACEFUL_TIMEOUT:-30} --access-logfile - --access-logformat '%(h)s %(t)s \"%(m)s %(H)s\" %(s)s %(b)s %(L)s' --error-logfile - app:app"]
