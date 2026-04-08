.PHONY: help local-db-start local-db-stop local-db-seed local-db-reset local-api-start test sam-build deploy-api logs-api smoke-test seed-ideas

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

local-db-start:  ## Start DynamoDB Local via Docker
	docker compose up -d
	@echo "DynamoDB Local running on http://localhost:8000"

local-db-stop:  ## Stop DynamoDB Local
	docker compose down

local-db-seed:  ## Create tables and seed icebreakers
	DYNAMODB_ENDPOINT=http://localhost:8000 pipenv run python scripts/seed_local.py

local-db-reset:  ## Drop and recreate local tables
	@echo "Dropping local tables..."
	-aws dynamodb delete-table --table-name icebreakers --endpoint-url http://localhost:8000 2>/dev/null
	-aws dynamodb delete-table --table-name conversation_turns --endpoint-url http://localhost:8000 2>/dev/null
	@echo "Re-seeding..."
	$(MAKE) local-db-seed

local-api-start:  ## Start API server locally via SAM (port 3000)
	sam local start-api --port 3000 --env-vars env.local.json

test:  ## Run API unit tests
	pipenv run python -m pytest tests/ -v

sam-build:  ## Build Lambda package
	sam build

deploy-api:  ## SAM build + deploy
	sam build && sam deploy

logs-api:  ## Tail CloudWatch logs for T12nApiFunction
	sam logs -n T12nApiFunction --tail

smoke-test:  ## Hit key endpoints and verify responses
	pipenv run python ../scripts/smoke_test.py

seed-ideas:  ## Seed conversation_ideas table (production)
	pipenv run python scripts/seed_ideas.py
