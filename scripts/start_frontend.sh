#!/bin/bash
# Frontend启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib_common.sh"

echo "🚀 Starting Novel System Frontend..."

cd "$PROJECT_ROOT"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

if [ ! -d "$FRONTEND_DIR" ]; then
    log_error "frontend directory not found: $FRONTEND_DIR"
    exit 1
fi

cd "$FRONTEND_DIR"

if [ ! -f "package.json" ]; then
    log_error "package.json not found in frontend directory"
    exit 1
fi

if [ ! -d "node_modules" ]; then
    log_step "Installing frontend dependencies..."
    npm install
fi

check_backend_health || log_warn "Backend not available, but continuing..."

log_info "Starting Vite dev server..."
exec npm run dev -- --host 0.0.0.0 --port 3000
