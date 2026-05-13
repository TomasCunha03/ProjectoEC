-include .env
export

# Cursor (and some IDE terminals) export MAKE as the editor binary; recursive $(MAKE) must stay GNU Make.
override MAKE := $(shell command -v gmake 2>/dev/null || command -v make 2>/dev/null || printf '%s\n' make)

up:
	docker compose up --build -d --wait

down:
	docker compose down

logs:
	docker compose logs -f

ingest:
	docker compose run app python scripts/run_ingestion.py

list-llms:
	docker compose exec ollama ollama list

pull-model:
	docker compose exec ollama ollama pull $(LLM_MODEL)

git-stats:
	@python scripts/git_stats.py

eval:
	PYTHONPATH=apps:src python -m api.eval

lint:
	ruff check .

fix:
	ruff check . --fix

format:
	ruff format .

check-all: lint format

init-env:
	@if [ ! -f .env ]; then cp .env.example .env; fi

download-data:
	python scripts/download_data.py

clean-all:
	docker compose down -v --remove-orphans

bootstrap:
	$(MAKE) download-data
	$(MAKE) up
	$(MAKE) ingest
	$(MAKE) pull-model

setup:
	$(MAKE) init-env
	$(MAKE) bootstrap

prod: setup