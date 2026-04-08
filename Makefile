.PHONY: help start-all local-db-start local-db-stop local-db-seed local-db-reset local-api-start local-ui-start test sam-build deploy-api deploy-ui logs-api smoke-test

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

start-all: local-db-start local-api-start  ## Start local DynamoDB + API

local-db-start:  ## Start DynamoDB Local via Docker
	$(MAKE) -C api local-db-start

local-db-stop:  ## Stop DynamoDB Local
	$(MAKE) -C api local-db-stop

local-db-seed:  ## Create tables and seed icebreakers
	$(MAKE) -C api local-db-seed

local-db-reset:  ## Drop and recreate local tables
	$(MAKE) -C api local-db-reset

local-api-start:  ## Start API server locally (port 3000)
	$(MAKE) -C api local-api-start

local-ui-start:  ## Start Vite dev server (port 5173)
	cd ui && npm run dev

test:  ## Run API unit tests
	$(MAKE) -C api test

sam-build:  ## Build Lambda package
	$(MAKE) -C api sam-build

deploy-api:  ## SAM build + deploy
	$(MAKE) -C api deploy-api

deploy-ui:  ## Vite build + S3 sync + CloudFront invalidate
	cd ui && npm run build
	aws s3 sync ui/dist/ s3://$$S3_BUCKET --delete
	aws cloudfront create-invalidation --distribution-id $$CLOUDFRONT_DISTRIBUTION_ID --paths "/*"

logs-api:  ## Tail CloudWatch logs for WhoIsMeApiFunction
	$(MAKE) -C api logs-api

smoke-test:  ## Hit key endpoints and verify responses
	SMOKE_BASE_URL=https://api.whoisme.io pipenv run python scripts/smoke_test.py
