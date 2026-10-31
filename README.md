# Fazenda — Gerenciador de Rebanho

Boilerplate full-stack em Python construído sobre uma **arquitetura em camadas limpa e modular**, preparado para desenvolvimento local conteinerizado e deploy contínuo no **Render** com banco de dados PostgreSQL no **Supabase**.

---

## Stack Tecnológica

- **Runtime:** Python 3.13+
- **Gerenciador de Dependências:** Poetry
- **Web Framework:** FastAPI + Uvicorn
- **Frontend SSR/Reativo:** Jinja2 + HTMX + Tailwind CSS (via CDN)
- **ORM & Migrações:** SQLAlchemy 2.0 (`DeclarativeBase`) + Alembic + `psycopg` v3
- **Configuração:** Pydantic Settings (`.env`)
- **Testes:** Pytest + HTTPX (`TestClient`)
- **Infraestrutura Local:** Docker + Docker Compose (`compose.yml`) + Makefile

---

## Estrutura de Diretórios

```text
.
├── app/
│   ├── application/
│   │   ├── routers/
│   │   │   ├── health.py       # GET /health (status do app e SELECT 1 no banco)
│   │   │   └── home.py         # GET / e GET /htmx/ping (SSR com Jinja2 + HTMX)
│   │   └── schemas/            # DTOs / Schemas Pydantic
│   ├── domain/
│   │   ├── core/
│   │   │   └── config.py       # Pydantic Settings (normalização automática de DATABASE_URL)
│   │   ├── models/
│   │   │   └── base.py         # DeclarativeBase do SQLAlchemy 2.0
│   │   ├── repositories/       # Contratos/Abstrações de repositórios
│   │   └── use_cases/          # Casos de uso do domínio
│   ├── infrastructure/
│   │   └── database.py         # Engine, SessionLocal e dependência get_db
│   ├── templates/
│   │   ├── base.html           # Layout base HTML5 (Tailwind CSS + HTMX via CDN)
│   │   └── home.html           # Página inicial com interação HTMX
│   └── main.py                 # Entrypoint e fábrica da aplicação FastAPI
├── alembic/                    # Ambiente de migrações conectado ao Base.metadata
├── tests/                      # Testes funcionais com Pytest e SQLite em memória
├── Dockerfile
├── compose.yml
├── Makefile
├── pyproject.toml
└── .env.example
```

---

## Execução Local

### 1. Variáveis de Ambiente

Copie o arquivo de exemplo para criar seu `.env` local:

```bash
cp .env.example .env
```

### 2. Usando Docker Compose (Recomendado para Ambiente Completo)

Sobe o banco **PostgreSQL 17** e a aplicação **FastAPI** com hot-reload mapeado na porta `8000`:

```bash
# Subir os serviços em background
make up

# Aplicar migrações no banco do container (opcional)
docker compose exec app alembic upgrade head

# Derrubar os serviços
make down
```

### 3. Usando Poetry + Makefile

Com o **Poetry** e **Python 3.13+** instalados localmente:

```bash
# Instalar dependências (produção + desenvolvimento) via Poetry
make install

# Executar a suíte de testes (Pytest)
make test

# Aplicar migrações do banco configurado no .env
make migrate

# Iniciar o servidor local com hot-reload em http://localhost:8000
make run
```

### Rotas Disponíveis

- `http://localhost:8000/` — Interface inicial SSR com teste interativo HTMX (`GET /htmx/ping`)
- `http://localhost:8000/health` — Healthcheck validando conectividade com o banco (`SELECT 1`)
- `http://localhost:8000/docs` — Documentação interativa OpenAPI (Swagger UI)

---

## Deploy no Render + PostgreSQL no Supabase

### 1. Configuração do Banco no Supabase
1. Acesse **Project Settings > Database > Connection string** no painel do Supabase.
2. Copie a URI de conexão (modo *Transaction* na porta `6543` ou *Session* na porta `5432`).
   - Nota: O módulo `app/domain/core/config.py` converte automaticamente prefixos `postgres://` ou `postgresql://` para `postgresql+psycopg://`.

### 2. Configuração do Web Service no Render
Crie um novo **Web Service** conectado ao repositório Git com os seguintes parâmetros:

- **Runtime:** `Python 3` (ou `Docker`, caso prefira deploy via `Dockerfile`)
- **Build Command:**
  ```bash
  poetry install --only main && poetry run alembic upgrade head
  ```
- **Start Command:**
  ```bash
  poetry run uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- **Health Check Path:** `/health`

### 3. Variáveis de Ambiente no Render
Adicione no painel **Environment** do Render:

| Variável | Valor Exemplo |
| :--- | :--- |
| `PYTHON_VERSION` | `3.13.0` |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `DATABASE_URL` | `postgresql://postgres.[ref]:[senha]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres` |
