FROM python:3.11-slim

# Создаём рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y netcat-openbsd libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Копируем код
COPY app/ app/

# Открываем порт
EXPOSE 8000

COPY alembic.ini .
COPY alembic ./alembic
COPY migrations.sh /app/migrations.sh
RUN chmod +x /app/migrations.sh

# По умолчанию запускаем FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
