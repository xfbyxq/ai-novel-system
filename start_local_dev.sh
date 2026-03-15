#!/bin/bash

# 本地开发模式启动脚本 - 不使用 Docker 打包
# 用法：./start_local_dev.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}检查基础服务...${NC}"

# 检查 PostgreSQL
if ! docker ps | grep -q novel_postgres; then
    echo -e "${YELLOW}启动 PostgreSQL...${NC}"
    docker-compose -f docker-compose.dev.yml up -d postgres
    sleep 5
fi

# 检查 Redis
if ! docker ps | grep -q novel_redis; then
    echo -e "${YELLOW}启动 Redis...${NC}"
    docker-compose -f docker-compose.dev.yml up -d redis
    sleep 2
fi

echo -e "${GREEN}✓ 基础服务已就绪${NC}"

# 检查数据库表
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
    echo -e "${YELLOW}初始化数据库表...${NC}"
    if [ -f "./create_tables.sh" ]; then
        ./create_tables.sh
    fi
fi

echo ""
echo -e "${BLUE}本地开发启动命令：${NC}"
echo "  后端：cd /Users/sanyi/code/python/novel_system && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo "  前端：cd /Users/sanyi/code/python/novel_system/frontend && npm run dev"
echo ""

echo -e "${GREEN}✓ 本地开发环境准备就绪${NC}"
echo ""
echo -e "${GREEN}访问地址：${NC}"
echo "  前端：http://localhost:3000"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""