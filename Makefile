.PHONY: up down logs build build-sandbox db-migrate db-upgrade db-downgrade init

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

build-sandbox:
	docker build -t agent-sandbox:latest ./agent-sandbox

db-migrate:
	docker compose run --rm api alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	docker compose run --rm api alembic upgrade head

db-downgrade:
	docker compose run --rm api alembic downgrade -1

init: build build-sandbox
	docker compose up -d postgres redis
	sleep 5
	docker compose run --rm api alembic upgrade head
	docker compose up -d
