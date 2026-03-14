#!/bin/bash
# Frontend启动脚本
set -e

echo "🚀 Starting Novel System Frontend..."

# 切换到frontend目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."  # 返回项目根目录

FRONTEND_DIR="$SCRIPT_DIR/../frontend"
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ frontend directory not found: $FRONTEND_DIR"
    exit 1
fi

cd "$FRONTEND_DIR"

# 检查package.json
if [ ! -f "package.json" ]; then
    echo "❌ package.json not found in frontend directory"
    exit 1
fi

# 检查node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# 检查后端服务
echo "📝 Checking backend service..."
BACKEND_AVAILABLE=$(curl -s http://localhost:8000/health > /dev/null 2>&1)
if [ $? -ne 0 ]; then
    echo "⚠️  Backend not available on http://localhost:8000"
    echo "   Start it with: cd backend && uvicorn main:app --reload"
    echo "   Or: ./scripts/start_backend.sh"
fi
echo "✅ Backend is ready (or starting)..."

# 启动前端开发服务器
echo "🚀 Starting Vite dev server..."
exec npm run dev -- --host 0.0.0.0 --port 3000
