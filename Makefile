up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

ingest:
	docker compose run app python scripts/run_ingestion.py

list-llms:
	docker compose exec ollama ollama list

pull-model:
	docker compose exec ollama ollama pull $(MODEL)

git-stats:
	@python scripts/git_stats.py

lint:
	ruff check .

fix:
	ruff check . --fix

format:
	ruff format .

check-all: lint format