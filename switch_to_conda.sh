#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
ENV_NAME="store-map-env"

if ! command -v conda >/dev/null 2>&1; then
  echo "Conda 未找到，请先安装 Miniconda/Conda。" >&2
  exit 1
fi

echo "创建/检查 Conda 环境 '$ENV_NAME'（Python 3.9）..."
if conda info --envs | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "环境已存在，跳过创建。"
else
  conda create -y -n "$ENV_NAME" python=3.9
fi

echo "在 '$ENV_NAME' 中安装依赖..."
conda run -n "$ENV_NAME" pip install -r "$REQ_FILE"

if [ -d "$PROJECT_ROOT/.venv" ]; then
  echo "删除本地 .venv 以瘦身..."
  rm -rf "$PROJECT_ROOT/.venv"
else
  echo "未找到 .venv，无需删除。"
fi

cat <<'EOF'

后续 Git 操作（在项目根目录执行）：
  git init
  git add .
  git commit -m "Initial commit"
  git remote add origin <your-github-url>
  git push -u origin main

使用 Conda 环境：
  conda activate store-map-env
EOF
