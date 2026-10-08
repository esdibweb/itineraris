FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are served by WhiteNoise from the image; media (avatars) lives in a volume
RUN SECRET_KEY=build-only DJANGO_ALLOWED_HOSTS=localhost python manage.py collectstatic --noinput \
    && mkdir -p /app/media \
    && chown app:app /app/media \
    && chmod +x /app/entrypoint.sh

USER app
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "home.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
