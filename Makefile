.PHONY: help install run test up down migrate revision

POETRY ?= poetry

help: ## Exibe os comandos disponíveis no Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências do projeto (produção + desenvolvimento) via Poetry
	$(POETRY) install

run: ## Inicia o servidor local em modo de desenvolvimento (hot-reload)
	$(POETRY) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Executa a suíte de testes automatizados com Pytest
	$(POETRY) run pytest

up: ## Sobe os containers locais (app + PostgreSQL 17) em background
	docker compose up --build -d

down: ## Para e remove os containers locais
	docker compose down

migrate: ## Aplica todas as migrações pendentes no banco de dados (alembic upgrade head)
	$(POETRY) run alembic upgrade head

revision: ## Gera uma nova revisão de migração (uso: make revision m="descricao")
	$(POETRY) run alembic revision --autogenerate -m "$(m)"
