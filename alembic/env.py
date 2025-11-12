import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

from app.models.base import Base
from app.models import user  # импортируй все модели, которые нужны в миграциях


# Alembic Config
config = context.config
fileConfig(config.config_file_name)


# Метаданные из Base
target_metadata = Base.metadata


# Используем переменную окружения ALEMBIC_DATABASE_URL
def get_url():
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if not url:
        url = os.getenv("PG_DSN")
    if not url:
        raise RuntimeError("ALEMBIC_DATABASE_URL or PG_DSN must be set")
    return url



def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # ⬅ если хочешь отслеживать изменения типов
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # ⬅ если нужно
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
