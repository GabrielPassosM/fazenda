.PHONY: help install run test compose-up compose-down migrate revision

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
UV ?= $(shell command -v uv 2>/dev/null || ( [ -x "$(HOME)/.local/bin/uv" ] && echo "$(HOME)/.local/bin/uv" ) || ( [ -x "/opt/homebrew/bin/uv" ] && echo "/opt/homebrew/bin/uv" ))

help: ## Exibe os comandos disponíveis no Makefile
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências do projeto (produção + desenvolvimento)
	@if [ -n "$(UV)" ]; then \
		$(UV) pip install -e ".[dev]"; \
	else \
		$(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1 || true; \
		$(PYTHON) -m pip install --upgrade pip && $(PYTHON) -m pip install -e ".[dev]"; \
	fi

run: ## Inicia o servidor local em modo de desenvolvimento (hot-reload)
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Executa a suíte de testes automatizados com Pytest
	$(PYTHON) -m pytest

compose-up: ## Sobe os containers locais (app + PostgreSQL 17) em background
	docker compose up --build -d

compose-down: ## Para e remove os containers locais
	docker compose down

migrate: ## Aplica todas as migrações pendentes no banco de dados (alembic upgrade head)
	$(PYTHON) -m alembic upgrade head

revision: ## Gera uma nova revisão de migração (uso: make revision m="descricao")
	$(PYTHON) -m alembic revision --autogenerate -m "$(m)"
