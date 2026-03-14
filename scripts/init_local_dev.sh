#!/bin/bash
# 本地开发环境初始化脚本
# 初始化Python虚拟环境和依赖
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."  # 确保在项目根目录

echo "🔧 Initializing Local Development Environment..."

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1)
echo "🚀 Python version: $PYTHON_VERSION"

# 检查Poetry是否存在
if ! command -v poetry &> /dev/null; then
    echo "⚠️  Poetry not found, installing..."
    pip install poetry
fi

# 检查是否已经有虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

# 安装Python依赖
echo "Installing Python dependencies..."
if command -v poetry &> /dev/null; then
    poetry install
else
    pip install -e .
fi

# 创建.env文件 (如果不存在)
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ Please configure .env with your settings"
    echo "   - Set your DASHSCOPE_API_KEY"
    echo "   - Adjust DATABASE_URL if needed (default: localhost:5434)"
fi

# 检查并设置DASHSCOPE_API_KEY
if [ -f ".env" ]; then
    API_KEY=$(grep "DASHSCOPE_API_KEY" .env | cut -d'=' -f2)
    if [ "$API_KEY" == "your-api-key-here" ] || [ -z "$API_KEY" ]; then
        echo "⚠️  Please set your DASHSCOPE_API_KEY in .env file"
    fi
fi

# 创建数据库表 (使用本地连接)
echo "Creating database tables..."
alembic upgrade head || {
    echo "⚠️  Migration failed. Make sure PostgreSQL is running on localhost:5434"
    echo "   You can start it with: docker-compose up -d postgres"
    exit 1
}

# 安装前端依赖 (可选)
echo ""
echo "📦 Would you like to install frontend dependencies? (y/n)"
read -p "> " INSTALL_FRONTEND
if [ "$INSTALL_FRONTEND" == "y" ]; then
    cd frontend
    npm install
    cd ..
fi

echo ""
echo "✅ Local development environment is ready!"
echo ""
echo "🚀 Start services:"
echo "   Backend:  ./scripts/start_backend.sh"
echo "   Frontend: ./scripts/start_frontend.sh"
echo ""
echo "🧪 Run tests:"
echo "   pytest"
