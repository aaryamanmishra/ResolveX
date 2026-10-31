#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Running ResolveX AI Quality Gates"
echo "=========================================================="

echo "[1/4] Running Ruff Linter..."
.venv/bin/ruff check .

echo "[2/4] Checking Code Formatting..."
.venv/bin/ruff format --check .

echo "[3/4] Running Static Typing (mypy)..."
.venv/bin/mypy backend/app/domain backend/app/security backend/app/providers backend/app/graph backend/app/services backend/app/api backend/app/models backend/app/policies

echo "[4/4] Running Contract and Unit Tests..."
.venv/bin/pytest backend/tests -v

echo "=========================================================="
echo " All Quality Gates Passed Successfully!"
echo "=========================================================="
