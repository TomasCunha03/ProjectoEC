include .env
export

up:
	docker compose up --build -d

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

lint:
	ruff check .

fix:
	ruff check . --fix

format:
	ruff format .

check-all: lint format

init-env:
	cp .env.example .env

download-data:
	python scripts/download_data.py

clean-all:
	docker compose down -v --remove-orphans

setup:
	make init-env
	make download-data
	make up
	sleep 10
	make ingest
	make pull-model 