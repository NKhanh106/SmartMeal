import os

def create_structure(base_path):
    structure = [
        "apps/web/public",
        "apps/web/src/app",
        "apps/web/src/components",
        "apps/web/src/features",
        "apps/web/src/hooks",
        "apps/web/src/lib",
        "apps/web/src/services",
        "apps/web/src/store",
        "apps/web/src/styles",
        "apps/web/src/types",
        "apps/web/tests",
        
        "apps/api/app/api/v1/endpoints",
        "apps/api/app/core",
        "apps/api/app/db",
        "apps/api/app/models",
        "apps/api/app/schemas",
        "apps/api/app/repositories",
        "apps/api/app/services",
        "apps/api/app/integrations",
        "apps/api/app/ai",
        "apps/api/app/domain",
        "apps/api/app/utils",
        "apps/api/app/workers",
        "apps/api/tests",
        "apps/api/alembic",

        "packages/shared-types",
        "packages/ui",
        "packages/config-eslint",
        "packages/config-typescript",
        "packages/docs-snippets",

        "docs/architecture",
        "docs/api",
        "docs/database",
        "docs/deployment",
        "docs/onboarding",
        "docs/adr",
        "docs/conventions",

        "infra/docker",
        "infra/nginx",
        "infra/scripts",
        "infra/monitoring",
        "infra/compose",

        ".github/workflows",
    ]

    files = {
        "apps/web/src/middleware.ts": "// Middleware logic\n",
        "apps/web/package.json": "{\n  \"name\": \"@smartmeal/web\",\n  \"version\": \"1.0.0\",\n  \"private\": true\n}\n",
        "apps/web/next.config.ts": "import type { NextConfig } from 'next';\n\nconst nextConfig: NextConfig = {};\nexport default nextConfig;\n",
        
        "apps/api/app/api/v1/router.py": "from fastapi import APIRouter\n\napi_router = APIRouter()\n",
        "apps/api/app/main.py": "from fastapi import FastAPI\n\napp = FastAPI(title=\"SmartMeal API\")\n\n@app.get(\"/\")\ndef root():\n    return {\"message\": \"Welcome to SmartMeal API\"}\n",
        "apps/api/app/dependencies.py": "# Depends go here\n",
        "apps/api/pyproject.toml": "[tool.poetry]\nname = \"api\"\nversion = \"0.1.0\"\ndescription = \"SmartMeal API\"\nauthors = [\"SmartMeal <admin@smartmeal.com>\"]\n",
        "apps/api/Dockerfile": "FROM python:3.11-slim\n# Setup goes here\n",

        ".env.example": "NODE_ENV=development\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD=password\nPOSTGRES_DB=smartmeal\nDATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}\n",
        "Makefile": "install:\n\tpnpm install\n\ndev-web:\n\tpnpm --filter web dev\n\ndev-api:\n\tpnpm --filter api dev\n",
        "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n  - 'packages/*'\n",
        "turbo.json": "{\n  \"$schema\": \"https://turbo.build/schema.json\",\n  \"pipeline\": {\n    \"build\": {\n      \"dependsOn\": [\"^build\"],\n      \"outputs\": [\".next/**\", \"!.next/cache/**\"]\n    },\n    \"dev\": {\n      \"cache\": false,\n      \"persistent\": true\n    }\n  }\n}\n"
    }

    print("Khởi tạo cấu trúc thư mục...")
    for folder in structure:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)
        # Create an empty .gitkeep so empty folders are preserved
        with open(os.path.join(base_path, folder, ".gitkeep"), "w") as f:
            pass
            
    print("Khởi tạo các file cấu hình và boilerplate...")
    for file_path, content in files.items():
        full_path = os.path.join(base_path, file_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    create_structure(base_dir)
    print(f"Hoàn thành scaffolding workspace tại {base_dir}!")
