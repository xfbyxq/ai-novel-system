#!/bin/bash
# Backend启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_common.sh"

echo "🚀 Starting Novel System Backend..."

cd "$PROJECT_ROOT"

# 检查.env文件
check_env_file || exit 1

# 检查DASHSCOPE_API_KEY
check_required_env "DASHSCOPE_API_KEY" || exit 1

# 检查PostgreSQL连接
check_postgres_docker || exit 1

# 检查Redis连接
check_redis_docker || exit 1

# 运行数据库迁移
run_migrations

# 启动后端
log_info "Starting backend server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
