#!/bin/bash
# 本地开发环境初始化脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_common.sh"

echo "🔧 Initializing Local Development Environment..."

cd "$PROJECT_ROOT"

# 检查Python版本
log_step "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
log_info "Python version: $PYTHON_VERSION"

# 检查Poetry是否存在
if ! command -v poetry &> /dev/null; then
    log_warn "Poetry not found, installing..."
    pip install poetry
fi

# 检查是否已经有虚拟环境
if [ ! -d "venv" ]; then
    log_step "Creating virtual environment..."
    python3 -m venv venv
fi

# 激活虚拟环境
log_step "Activating virtual environment..."
source venv/bin/activate

# 安装Python依赖
log_step "Installing Python dependencies..."
if command -v poetry &> /dev/null; then
    poetry install
else
    pip install -e .
fi

# 创建.env文件 (如果不存在)
if [ ! -f ".env" ]; then
    log_step "Creating .env file from .env.example..."
    cp .env.example .env
    log_warn "Please configure .env with your settings"
    log_info "Set your DASHSCOPE_API_KEY"
fi

# 检查并设置DASHSCOPE_API_KEY
if [ -f ".env" ]; then
    check_required_env "DASHSCOPE_API_KEY" || true
fi

# 启动基础服务
start_base_services_docker

# 运行数据库迁移
run_migrations

# 安装前端依赖
log_step "Installing frontend dependencies..."
cd "$PROJECT_ROOT/frontend"
npm install
cd "$PROJECT_ROOT"

echo ""
log_info "Local development environment is ready!"
echo ""
echo "🚀 Start services:"
echo "   Backend:  ./scripts/start_backend.sh"
echo "   Frontend: ./scripts/start_frontend.sh"
echo "   Both:     ./scripts/start_dev_all.sh"
echo ""
