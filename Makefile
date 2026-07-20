PYTHON ?= python

.PHONY: setup migrate test lint format-check run seed-demo smoke docker-up docker-down

setup:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) manage.py migrate

migrate:
	$(PYTHON) manage.py migrate

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

run:
	$(PYTHON) manage.py runserver

seed-demo:
	$(PYTHON) manage.py seed_demo

smoke:
	docker compose exec web /app/scripts/smoke_report.sh

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
