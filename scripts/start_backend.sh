#!/bin/bash
# Backend启动脚本
set -e

echo "🚀 Starting Novel System Backend..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."  # 返回项目根目录

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please run init_local_dev.sh first."
    exit 1
fi

# 检查DASHSCOPE_API_KEY
API_KEY=$(grep "DASHSCOPE_API_KEY" .env | cut -d'=' -f2)
if [ "$API_KEY" == "your-api-key-here" ] || [ -z "$API_KEY" ]; then
    echo "⚠️  Please set your DASHSCOPE_API_KEY in .env file"
    exit 1
fi

# 检查PostgreSQL连接
echo "📝 Checking PostgreSQL connection..."
# 使用docker exec而不是Python，避免依赖问题
if ! docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL not ready"
    echo "   Wait a moment and try again, or start with: docker-compose up -d postgres"
    exit 1
fi
echo "✅ PostgreSQL is ready"

# 检查Redis连接
echo "Checking Redis connection..."
if ! docker exec novel_redis redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis not available"
    echo "   Start it with: docker-compose up -d redis"
    exit 1
fi
echo "✅ Redis is ready"

# 升级数据库
echo "🔧 Running database migrations..."
alembic upgrade head || {
    echo "⚠️  Migration failed, continuing anyway..."
}

# 启动后端
echo "🚀 Starting backend server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
