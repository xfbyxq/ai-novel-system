#!/bin/bash

# 小说生成系统 - 一键完整部署脚本（含数据库迁移）
# 用法：./deploy_complete.sh [选项]
# 选项:
#   --clean    清理所有容器和镜像（全新部署）
#   --migrate  仅执行数据库迁移
#   --restart  仅重启服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 配置
COMPOSE_FILE="docker-compose.yml"
MIGRATION_FILE="docker-compose.migration.yml"
CONTAINER_PREFIX="novel_"

# 显示帮助
show_help() {
    echo "用法：$0 [选项]"
    echo ""
    echo "选项:"
    echo "  --clean    清理所有容器和镜像（全新部署）"
    echo "  --migrate  仅执行数据库迁移"
    echo "  --restart  仅重启服务"
    echo "  --help     显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 标准部署"
    echo "  $0 --clean            # 全新部署"
    echo "  $0 --migrate          # 仅迁移数据库"
    echo ""
}

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误：Docker 未安装${NC}"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        echo -e "${RED}错误：Docker 未运行${NC}"
        exit 1
    fi
}

# 清理旧容器和镜像
clean_old() {
    echo -e "${YELLOW}[清理] 停止并删除旧容器...${NC}"
    docker-compose -f $COMPOSE_FILE down -v
    
    echo -e "${YELLOW}[清理] 删除旧镜像...${NC}"
    docker rmi novel_system-backend novel_system-frontend 2>/dev/null || true
    
    echo -e "${GREEN}✓ 清理完成${NC}"
    echo ""
}

# 执行数据库迁移
run_migration() {
    echo -e "${YELLOW}[迁移] 执行数据库迁移...${NC}"
    
    # 检查数据库容器
    if ! docker ps | grep -q novel_postgres; then
        echo -e "${RED}错误：数据库容器未运行${NC}"
        echo -e "${YELLOW}请先启动数据库：docker-compose up -d postgres${NC}"
        exit 1
    fi
    
    # 等待数据库就绪
    echo -e "${BLUE}等待数据库就绪...${NC}"
    for i in {1..10}; do
        if docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
            echo -e "${GREEN}✓ 数据库已就绪${NC}"
            break
        fi
        sleep 2
    done
    
    # 方法 1: 使用 Alembic
    echo -e "${BLUE}尝试 Alembic 自动迁移...${NC}"
    if docker ps | grep -q novel_backend; then
        if docker exec novel_backend alembic upgrade head 2>/dev/null; then
            echo -e "${GREEN}✓ Alembic 迁移成功${NC}"
            return 0
        fi
    fi
    
    # 方法 2: 手动 SQL 迁移
    echo -e "${YELLOW}使用手动 SQL 迁移...${NC}"
    
    docker exec -i novel_postgres psql -U novel_user -d novel_system << 'EOSQL'
BEGIN;

-- 添加 outline_task 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_task'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_task JSONB DEFAULT '{}';
        RAISE NOTICE '✓ 已添加：outline_task';
    END IF;
END $$;

-- 添加 outline_validation 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_validation'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_validation JSONB DEFAULT '{}';
        RAISE NOTICE '✓ 已添加：outline_validation';
    END IF;
END $$;

-- 添加 outline_version 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_version'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_version VARCHAR(50);
        RAISE NOTICE '✓ 已添加：outline_version';
    END IF;
END $$;

COMMIT;
EOSQL
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 手动迁移成功${NC}"
    else
        echo -e "${RED}✗ 迁移失败${NC}"
        exit 1
    fi
}

# 构建镜像
build_images() {
    echo -e "${YELLOW}[构建] 构建 Docker 镜像...${NC}"
    
    echo -e "${BLUE}构建后端镜像...${NC}"
    docker-compose build backend
    
    echo -e "${BLUE}构建前端镜像...${NC}"
    docker-compose build frontend
    
    echo -e "${GREEN}✓ 镜像构建完成${NC}"
    echo ""
}

# 启动服务
start_services() {
    echo -e "${YELLOW}[启动] 启动所有服务...${NC}"
    
    # 先启动基础服务
    docker-compose up -d postgres redis
    echo -e "${BLUE}等待基础服务启动...${NC}"
    sleep 5
    
    # 检查数据库是否为空
    TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
    
    if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
        echo -e "${YELLOW}数据库为空，创建所有表...${NC}"
        if [ -f "./create_tables.sh" ]; then
            ./create_tables.sh
        else
            run_migration
        fi
    else
        echo -e "${GREEN}数据库已有 $TABLE_COUNT 个表${NC}"
        # 执行可能的迁移
        run_migration
    fi
    
    # 启动应用服务
    docker-compose up -d backend frontend
    echo -e "${BLUE}等待应用服务启动...${NC}"
    sleep 10
    
    echo -e "${GREEN}✓ 所有服务已启动${NC}"
    echo ""
}

# 检查服务状态
check_status() {
    echo -e "${CYAN}服务状态：${NC}"
    docker-compose ps
    echo ""
    
    echo -e "${CYAN}访问地址：${NC}"
    echo -e "  前端：${BLUE}http://localhost:3000${NC}"
    echo -e "  后端 API: ${BLUE}http://localhost:8000${NC}"
    echo -e "  API 文档：${BLUE}http://localhost:8000/docs${NC}"
    echo ""
    
    echo -e "${CYAN}数据库迁移信息：${NC}"
    if docker ps | grep -q novel_postgres; then
        docker exec novel_postgres psql -U novel_user -d novel_system -t -c \
            "SELECT '新增字段：' || string_agg(column_name, ', ') 
             FROM information_schema.columns 
             WHERE table_name = 'chapters' 
             AND column_name IN ('outline_task', 'outline_validation', 'outline_version');"
    fi
    echo ""
}

# 主函数
main() {
    echo "============================================================"
    echo "小说生成系统 - 一键完整部署"
    echo "============================================================"
    echo ""
    
    check_docker
    
    case "${1:-}" in
        --clean)
            clean_old
            build_images
            start_services
            check_status
            ;;
        --migrate)
            run_migration
            echo -e "${GREEN}✓ 迁移完成${NC}"
            ;;
        --restart)
            echo -e "${YELLOW}[重启] 重启所有服务...${NC}"
            docker-compose restart
            sleep 10
            check_status
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        "")
            build_images
            start_services
            check_status
            ;;
        *)
            echo -e "${RED}错误：未知选项 '$1'${NC}"
            show_help
            exit 1
            ;;
    esac
}

# 执行
main "$@"
