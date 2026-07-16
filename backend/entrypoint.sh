#!/bin/sh
set -e

# Применяем миграции перед стартом (только backend; воркер не мигрирует схему).
if [ "${AIS_RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head
fi

exec "$@"
