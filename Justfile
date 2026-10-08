# デフォルトのアクション（引数なしで実行された場合）
# エージェントが迷ったときや、コミット前に全体を検証するための安全なフォールバックです。
default: check-all

# =============================================================================
# Agent API: 以下のコマンド群のみを CLAUDE.md でエージェントに露出させます
# =============================================================================

# コードの静的解析（Lint）を実行します
lint target="src/":
    @echo "==> Running Linter (Ruff) on {{target}}..."
    uv run ruff check {{target}}

# コードの自動フォーマットを実行します
format target="src/":
    @echo "==> Running Formatter (Ruff) on {{target}}..."
    uv run ruff format {{target}}
    uv run ruff check --fix {{target}}

# 静的型チェックを実行します
typecheck target="src/":
    @echo "==> Running Type Checker (Mypy) on {{target}}..."
    uv run mypy {{target}}

# テストを実行します
test target="tests/":
    @echo "==> Running Tests (Pytest) on {{target}}..."
    uv run pytest {{target}} -v

# 最小パイプラインをローカル環境で起動します
deploy query="AI regulation latest developments":
    @echo "==> Deploying Tsuzuri locally..."
    uv sync
    PYTHONPATH=src uv run python -m tsuzuri.cli run "{{query}}"

# 外部アプリ向けHTTP APIを起動します
api host="127.0.0.1" port="8000":
    @echo "==> Starting Tsuzuri API on {{host}}:{{port}}..."
    uv sync
    PYTHONPATH=src uv run uvicorn tsuzuri.api:app --host {{host}} --port {{port}}

# React frontendの開発サーバーを起動します
frontend-dev:
    @echo "==> Starting Tsuzuri frontend dev server..."
    npm --prefix frontend install
    npm --prefix frontend run dev

# React frontendをFastAPI配信用にビルドします
frontend-build:
    @echo "==> Building Tsuzuri frontend..."
    npm --prefix frontend install
    npm --prefix frontend run build

# Dockerイメージをビルドします
docker-build tag="tsuzuri:local":
    @echo "==> Building Docker image {{tag}}..."
    docker build -t {{tag}} .

# Docker ComposeでAPIと同梱SearXNGを起動します
docker-up:
    @echo "==> Starting Tsuzuri API and bundled SearXNG..."
    docker compose up --build

# Docker ComposeでAPIとSearXNGを停止します
docker-down:
    @echo "==> Stopping Tsuzuri API and bundled SearXNG..."
    docker compose down

# 既存の外部SearXNGを使い、同梱SearXNGを起動しません
docker-up-external:
    @echo "==> Starting Tsuzuri API with an external SearXNG endpoint..."
    docker compose -f docker-compose.yml up --build

# 外部SearXNG構成のみを停止します
docker-down-external:
    docker compose -f docker-compose.yml down

# APIコンテナから同梱SearXNGの実検索結果とエンジン障害を確認します
docker-search-smoke:
    docker compose exec -T tsuzuri-api python -c 'import json, urllib.parse, urllib.request; q = urllib.parse.urlencode({"q": "Linux kernel vulnerabilities", "format": "json", "categories": "general,news"}); result = json.load(urllib.request.urlopen("http://searxng:8080/search?" + q, timeout=20)); print("search_results=", len(result.get("results", [])), "unresponsive_engines=", result.get("unresponsive_engines", [])); assert result.get("results"), "SearXNG produced no search results"'

# =============================================================================
# 複合タスク (Pipelines)
# =============================================================================

# プルリクエスト作成前や、大きな変更の後にエージェントに実行させる一括検証
check-all: lint typecheck test
    @echo "==> [OK] All checks passed successfully."

# =============================================================================
# ユーティリティ (依存関係管理など)
# =============================================================================

# 依存関係の同期（.envrc からも呼ばれますが、明示的なAPIとしても提供）
sync:
    @echo "==> Syncing dependencies with uv..."
    uv sync
