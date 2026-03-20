#!/bin/bash
# =============================================================================
# 共享函数库 - 所有开发脚本共用
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# =============================================================================
# 颜色定义
# =============================================================================
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export RED='\033[0;31m'
export NC='\033[0m'

# =============================================================================
# 日志函数
# =============================================================================
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

log_step() {
    echo -e "${BLUE}📋${NC} $1"
}

# =============================================================================
# 检查 .env 文件
# =============================================================================
check_env_file() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_error ".env file not found. Please run init_local_dev.sh first."
        return 1
    fi
    log_info ".env file found"
    return 0
}

# =============================================================================
# 检查必需的环境变量
# =============================================================================
check_required_env() {
    local var_name="$1"
    local var_value

    var_value=$(grep "^${var_name}=" "$PROJECT_ROOT/.env" | cut -d'=' -f2-)

    if [ -z "$var_value" ] || [ "$var_value" == "your-api-key-here" ]; then
        log_error "Please set ${var_name} in .env file"
        return 1
    fi

    return 0
}

# =============================================================================
# 检查 PostgreSQL 连接 (Docker)
# =============================================================================
check_postgres_docker() {
    log_step "Checking PostgreSQL connection..."

    if ! docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
        log_warn "PostgreSQL not ready"
        log_info "Start it with: docker-compose up -d postgres"
        return 1
    fi

    log_info "PostgreSQL is ready"
    return 0
}

# =============================================================================
# 检查 PostgreSQL 连接 (本地)
# =============================================================================
check_postgres_local() {
    log_step "Checking PostgreSQL connection..."

    local PGHOST=$(grep "^DATABASE_URL=" "$PROJECT_ROOT/.env" | grep -oP '://[^:]+(?=:\d+)' | sed 's|://||')
    local PGPORT=$(grep "^DATABASE_URL=" "$PROJECT_ROOT/.env" | grep -oP ':\d+/' | tr -d ':/')
    PGPORT=${PGPORT:-5432}

    if ! pg_isready -h "$PGHOST" -p "$PGPORT" -U novel_user > /dev/null 2>&1; then
        log_warn "PostgreSQL not ready on $PGHOST:$PGPORT"
        log_info "Start it with: docker-compose up -d postgres"
        return 1
    fi

    log_info "PostgreSQL is ready"
    return 0
}

# =============================================================================
# 检查 Redis 连接 (Docker)
# =============================================================================
check_redis_docker() {
    log_step "Checking Redis connection..."

    if ! docker exec novel_redis redis-cli ping > /dev/null 2>&1; then
        log_warn "Redis not available"
        log_info "Start it with: docker-compose up -d redis"
        return 1
    fi

    log_info "Redis is ready"
    return 0
}

# =============================================================================
# 检查后端服务健康状态
# =============================================================================
check_backend_health() {
    log_step "Checking backend service..."

    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_info "Backend is ready"
        return 0
    fi

    log_warn "Backend not available on http://localhost:8000"
    return 1
}

# =============================================================================
# 运行数据库迁移
# =============================================================================
run_migrations() {
    log_step "Running database migrations..."

    cd "$PROJECT_ROOT"

    if alembic upgrade head; then
        log_info "Database migrations completed"
        return 0
    else
        log_warn "Migration failed, continuing anyway..."
        return 1
    fi
}

# =============================================================================
# 启动基础服务 (Docker)
# =============================================================================
start_base_services_docker() {
    log_step "Starting base services (PostgreSQL, Redis)..."

    cd "$PROJECT_ROOT"

    docker-compose -f docker-compose.dev.yml up -d postgres redis
    sleep 5

    # 等待 PostgreSQL 就绪
    for i in {1..10}; do
        if docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
            log_info "PostgreSQL is ready"
            break
        fi
        log_warn "Waiting for PostgreSQL... ($i/10)"
        sleep 2
    done

    log_info "Base services started"
}

# =============================================================================
# 初始化日志目录
# =============================================================================
init_log_dir() {
    mkdir -p "$PROJECT_ROOT/logs"
}
