#!/bin/bash
# 统一开发启动脚本 - 同时启动前端和后端
# 用法：./start_dev_all.sh [--backend-only] [--frontend-only]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_common.sh"

MODE="both"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend-only)
            MODE="backend"
            shift
            ;;
        --frontend-only)
            MODE="frontend"
            shift
            ;;
        -h|--help)
            echo "📋 统一开发启动脚本"
            echo ""
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --backend-only    只启动后端服务"
            echo "  --frontend-only   只启动前端服务"
            echo "  -h, --help        显示帮助信息"
            echo ""
            echo "默认: 同时启动前端和后端服务"
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Starting Novel System Development Environment..."
echo ""

cd "$PROJECT_ROOT"

# 启动基础服务
start_base_services_docker

# 启动后端
start_backend() {
    log_step "Starting backend..."
    "$SCRIPT_DIR/start_backend.sh" &
    BACKEND_PID=$!
    log_info "Backend started (PID: $BACKEND_PID)"
}

# 启动前端
start_frontend() {
    log_step "Starting frontend..."
    "$SCRIPT_DIR/start_frontend.sh" &
    FRONTEND_PID=$!
    log_info "Frontend started (PID: $FRONTEND_PID)"
}

case $MODE in
    both)
        start_backend
        start_frontend
        ;;
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
esac

echo ""
log_info "Development environment is running!"
echo ""
echo "📍 访问地址:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "📖 API 文档:"
echo "   Swagger UI: http://localhost:8000/docs"
echo ""
echo "🛑 停止服务: Ctrl+C"
echo ""

# 等待子进程
wait
