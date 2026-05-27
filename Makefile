.PHONY: setup build up down logs migrate seed workload collect collect-cpp demo demo-reset test test-backend test-collector test-frontend lint clean

setup:
	cp -n .env.example .env || true
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f backend collector

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec backend python -m app.demo.seed_data

workload:
	docker compose exec backend python -m app.demo.workload --iterations $(or $(N),500)

collect:
	docker compose exec backend python -m app.core.collector

collect-cpp:
	docker compose run --rm collector

demo: up
	@echo "waiting for db + kafka..."
	@sleep 6
	$(MAKE) migrate
	$(MAKE) seed
	docker compose exec -T db psql -U querylens -d querylens -c "SELECT pg_stat_statements_reset();" >/dev/null
	docker compose exec -T db psql -U querylens -d querylens -c "TRUNCATE querylens.query_regressions, querylens.query_reports, querylens.query_plans, querylens.query_metrics, querylens.query_fingerprints, querylens.collector_status CASCADE;" >/dev/null
	docker compose exec -T db psql -U querylens -d querylens -c "CREATE INDEX IF NOT EXISTS orders_user_id_idx ON demo.orders(user_id);" >/dev/null
	docker compose exec -T db psql -U querylens -d querylens -c "CREATE INDEX IF NOT EXISTS vector_items_embedding_hnsw_idx ON demo.vector_items USING hnsw (embedding vector_l2_ops);" >/dev/null
	docker compose exec backend python -m app.demo.workload --iterations 500 --no-drop-index
	$(MAKE) collect-cpp
	@echo "--- baseline collected from C++ collector ---"
	docker compose exec backend python -m app.demo.workload --iterations 1500
	$(MAKE) collect-cpp
	@echo "--- degraded collected from C++ collector ---"
	@echo "open http://localhost:3030 and http://localhost:3000"

demo-reset:
	docker compose exec -T db psql -U querylens -d querylens -c "SELECT pg_stat_statements_reset();" >/dev/null
	docker compose exec -T db psql -U querylens -d querylens -c "TRUNCATE querylens.query_regressions, querylens.query_reports, querylens.query_plans, querylens.query_metrics, querylens.query_fingerprints, querylens.collector_status CASCADE;" >/dev/null

test: test-backend test-collector test-frontend

test-backend:
	cd backend && .venv/bin/pytest tests/ -v

test-collector:
	docker compose run --rm collector --help

test-frontend:
	cd frontend && npm run build

lint:
	cd backend && .venv/bin/ruff check app/ tests/

clean:
	docker compose down -v
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/dist collector/build
