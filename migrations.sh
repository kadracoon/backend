#!/bin/bash

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z postgres 5432; do
  sleep 0.5
done

echo "Running Alembic migrations..."
echo "ALEMBIC_DATABASE_URL=$ALEMBIC_DATABASE_URL"
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
