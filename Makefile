COMPOSE		:= podman-compose
COMPOSE_FILE	:= docker-compose.yml
DC		:= $(COMPOSE) -f $(COMPOSE_FILE)

CHROMA_DIR	:= ./data/chroma

.DEFAULT_GOAL	:= help

.PHONY: all up build down stop restart logs ps status clean fclean re help

all: up ## Build and start all services (default)

up: ## Build images and start containers in detached mode
	@mkdir -p $(CHROMA_DIR)
	$(DC) up -d --build

build: ## Build or rebuild Docker images
	$(DC) build

down: ## Stop and remove containers and networks
	$(DC) down

stop: ## Stop running containers without removing them
	$(DC) stop

restart: down up ## Restart all services

logs: ## Follow container logs
	$(DC) logs -f

ps: ## List running containers
	$(DC) ps

status: ## Check FastAPI /status endpoint once ready
	@curl -fsS http://localhost:8000/status || echo "API not ready yet"

clean: down ## Stop containers and remove local ChromaDB index data
	rm -rf $(CHROMA_DIR)

fclean: ## Remove containers, named volumes (Ollama weights), local caches and images
	$(DC) down -v --remove-orphans
	podman system prune -af
	rm -rf $(CHROMA_DIR)


re: fclean up ## Full reset and rebuild from scratch

help: ## Display available Makefile targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'