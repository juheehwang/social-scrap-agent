
# ==============================================================================
# Installation & Setup
# ==============================================================================

# Install dependencies using uv package manager
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/0.8.13/install.sh | sh; source $$HOME/.local/bin/env; }
	@export UV_INDEX_STAGING_USERNAME=oauth2accesstoken; \
	export UV_INDEX_STAGING_PASSWORD=$$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token); \
	uv sync --dev

# Setup .env file with current gcloud project
setup-env:
	@PROJECT_ID=$$(gcloud config get-value project 2>/dev/null); \
	if [ -z "$$PROJECT_ID" ] || [ "$$PROJECT_ID" = "(unset)" ]; then \
		echo "❌ Error: No gcloud project set. Please run 'gcloud config set project <your-project-id>' first."; \
		exit 1; \
	fi; \
	echo "✅ Detected gcloud project: $$PROJECT_ID"; \
	if [ -f app/.env ]; then \
		if grep -q "^GOOGLE_CLOUD_PROJECT=" app/.env; then \
			sed -i "s/^GOOGLE_CLOUD_PROJECT=.*/GOOGLE_CLOUD_PROJECT=$$PROJECT_ID/" app/.env; \
			echo "✅ Updated GOOGLE_CLOUD_PROJECT in app/.env"; \
		else \
			echo "GOOGLE_CLOUD_PROJECT=$$PROJECT_ID" >> app/.env; \
			echo "✅ Appended GOOGLE_CLOUD_PROJECT to app/.env"; \
		fi; \
	else \
		echo "GOOGLE_CLOUD_PROJECT=$$PROJECT_ID" > app/.env; \
		echo "✅ Created app/.env with GOOGLE_CLOUD_PROJECT"; \
	fi


# ==============================================================================
# Playground Targets
# ==============================================================================

# Launch local dev playground
playground:
	@echo "==============================================================================="
	@echo "| 🚀 Starting your agent playground...                                        |"
	@echo "|                                                                             |"
	@echo "| 💡 Try asking: What's the weather in San Francisco?                         |"
	@echo "|                                                                             |"
	@echo "| 🔍 IMPORTANT: Select the 'app' folder to interact with your agent.          |"
	@echo "==============================================================================="
	@export UV_INDEX_STAGING_USERNAME=oauth2accesstoken; \
	export UV_INDEX_STAGING_PASSWORD=$$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token); \
	uv run adk web . --port 8501 --reload_agents

# ==============================================================================
# Backend Deployment Targets
# ==============================================================================

# Variables for Gemini Enterprise Registration
# Replace with your actual OAuth and Resource details
CLIENT_ID ?= client_id
CLIENT_SECRET ?= client_secret
AGENT_ENGINE_RESOURCE_NAME ?= $(shell jq -r '.remote_agent_engine_id // empty' deployment_metadata.json 2>/dev/null)

AUTH_ID_TO_USE := social_auth
GEMINI_ENTERPRISE_REGION := global
GEMINI_ENTERPRISE_APP_ID := gemini-enterprise-17742709_1774270925095
DISPLAY_NAME := social-scrap-agent

# Deploy the agent remotely
deploy:
	(uv export --no-hashes --no-header --no-dev --no-emit-project --no-annotate > app/app_utils/.requirements.txt 2>/dev/null || \
	uv export --no-hashes --no-header --no-dev --no-emit-project > app/app_utils/.requirements.txt) && \
	set -a; [ -f ../.env ] && . ../.env; set +a; \
	uv run -m app.app_utils.deploy \
		--source-packages=./app \
		--entrypoint-module=app.agent_engine_app \
		--entrypoint-object=agent_engine \
		--requirements-file=app/app_utils/.requirements.txt \
		--display-name=$(DISPLAY_NAME) \
		$(if $(AGENT_IDENTITY),--agent-identity) \
		$(if $(filter command line,$(origin SECRETS)),--set-secrets="$(SECRETS)")

# Alias for 'make deploy' for backward compatibility
backend: deploy

# Register the deployed agent with Gemini Enterprise (Vertex AI Search)
register-gemini-enterprise:
	$(eval PROJECT_ID := $(shell gcloud config get-value project))
	$(eval PROJECT_NUMBER := $(shell gcloud projects describe $(PROJECT_ID) --format='value(projectNumber)'))
	$(eval ACCESS_TOKEN := $(shell gcloud auth print-access-token))

	@if [ -z "$(AGENT_ENGINE_RESOURCE_NAME)" ]; then \
		echo "❌ Error: AGENT_ENGINE_RESOURCE_NAME is not set. Please deploy the agent first (make deploy)"; \
		exit 1; \
	fi

	@echo "🔍 Checking for existing Agent ID..."; \
	AGENT_ID=$$(curl -s -H "Authorization: Bearer $(ACCESS_TOKEN)" -H "Content-Type: application/json" -H "X-Goog-User-Project: $(PROJECT_ID)" "https://${GEMINI_ENTERPRISE_REGION}-discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/${GEMINI_ENTERPRISE_REGION}/collections/default_collection/engines/${GEMINI_ENTERPRISE_APP_ID}/assistants/default_assistant/agents" | jq -r '.agents[] | select(.displayName == "$(DISPLAY_NAME)") | .name | split("/") | last'); \
    echo "Extracted Agent ID: $$AGENT_ID"; \
	if [ -n "$$AGENT_ID" ] && [ "$$AGENT_ID" != "null" ]; then \
		echo "Existing Agent ($$AGENT_ID) found. Deleting for re-registration..."; \
		\
		echo "[1/2] Deleting Agent..."; \
		curl -X DELETE \
			-H "Authorization: Bearer $(ACCESS_TOKEN)" \
			"https://${GEMINI_ENTERPRISE_REGION}-discoveryengine.googleapis.com/v1alpha/projects/$(PROJECT_ID)/locations/${GEMINI_ENTERPRISE_REGION}/collections/default_collection/engines/${GEMINI_ENTERPRISE_APP_ID}/assistants/default_assistant/agents/$$AGENT_ID"; \
		\
		echo "\n[2/2] Deleting Authorization..."; \
		curl -X DELETE \
			-H "Authorization: Bearer $(ACCESS_TOKEN)" \
			-H "X-Goog-User-Project: $(PROJECT_ID)" \
			"https://$(GEMINI_ENTERPRISE_REGION)-discoveryengine.googleapis.com/v1alpha/projects/$(PROJECT_ID)/locations/$(GEMINI_ENTERPRISE_REGION)/authorizations/$(AUTH_ID_TO_USE)"; \
		\
		echo "\nCleanup complete."; \
	else \
		echo "No existing '$(DISPLAY_NAME)' Agent found. Proceeding with registration."; \
	fi

	@echo "1️⃣  Registering Authorization..."; \
	curl -X POST \
		-H "Authorization: Bearer $(ACCESS_TOKEN)" \
		-H "Content-Type: application/json" \
		-H "X-Goog-User-Project: $(PROJECT_ID)" \
		"https://$(GEMINI_ENTERPRISE_REGION)-discoveryengine.googleapis.com/v1alpha/projects/$(PROJECT_ID)/locations/$(GEMINI_ENTERPRISE_REGION)/authorizations?authorizationId=$(AUTH_ID_TO_USE)" \
		-d '{"name": "projects/$(PROJECT_NUMBER)/locations/$(GEMINI_ENTERPRISE_REGION)/authorizations/$(AUTH_ID_TO_USE)", "serverSideOauth2": {"clientId": "$(CLIENT_ID)", "clientSecret": "$(CLIENT_SECRET)", "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id=$(CLIENT_ID)&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive%20https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent", "tokenUri": "https://oauth2.googleapis.com/token"}}'

	@echo "\n2️⃣  Registering Agent..."; \
	curl -X POST \
		-H "Authorization: Bearer $(ACCESS_TOKEN)" \
		-H "Content-Type: application/json" \
		-H "X-Goog-User-Project: $(PROJECT_ID)" \
		"https://$(GEMINI_ENTERPRISE_REGION)-discoveryengine.googleapis.com/v1alpha/projects/$(PROJECT_ID)/locations/$(GEMINI_ENTERPRISE_REGION)/collections/default_collection/engines/$(GEMINI_ENTERPRISE_APP_ID)/assistants/default_assistant/agents" \
		-d '{"displayName": "$(DISPLAY_NAME)", "description": "Social Scrap Agent with ADK", "adk_agent_definition": { "provisioned_reasoning_engine": { "reasoning_engine": "$(AGENT_ENGINE_RESOURCE_NAME)" } }, "authorization_config": {"tool_authorizations": ["projects/$(PROJECT_NUMBER)/locations/$(GEMINI_ENTERPRISE_REGION)/authorizations/$(AUTH_ID_TO_USE)"]}}'

# ==============================================================================
# Infrastructure Setup
# ==============================================================================

# Set up development environment resources using Terraform
setup-dev-env:
	PROJECT_ID=$$(gcloud config get-value project) && \
	(cd deployment/terraform/dev && terraform init && terraform apply --var-file vars/env.tfvars --var dev_project_id=$$PROJECT_ID --auto-approve)

# ==============================================================================
# Testing & Code Quality
# ==============================================================================

# Run unit and integration tests
test:
	@export UV_INDEX_STAGING_USERNAME=oauth2accesstoken; \
	export UV_INDEX_STAGING_PASSWORD=$$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token); \
	uv sync --dev; \
	uv run pytest tests/unit && uv run pytest tests/integration

# Run code quality checks (codespell, ruff, mypy)
lint:
	@export UV_INDEX_STAGING_USERNAME=oauth2accesstoken; \
	export UV_INDEX_STAGING_PASSWORD=$$(gcloud auth application-default print-access-token 2>/dev/null || gcloud auth print-access-token); \
	uv sync --dev --extra lint; \
	uv run codespell; \
	uv run ruff check . --diff; \
	uv run ruff format . --check --diff; \
	uv run ty check .