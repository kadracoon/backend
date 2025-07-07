# Kadracoon Backend API
Main FastAPI backend serving game logic, user sessions, and scoring.

## Creating network
```sh
docker network create kadracoon-net
```

## Creating migration
```sh
docker compose run --rm web alembic revision --autogenerate -m "<migration_name>"
```