#!/bin/bash

# 开发环境快速启动脚本
# 用法：./start_dev.sh

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否已有容器运行
if docker ps | grep -q novel_backend; then
    echo -e "${YELLOW}检测到开发环境已在运行，停止现有服务...${NC}"
    docker-compose -f docker-compose.dev.yml down
fi

# 启动基础服务
echo -e "${YELLOW}启动基础服务（PostgreSQL, Redis）...${NC}"
docker-compose -f docker-compose.dev.yml up -d postgres redis
sleep 5

# 检查数据库
for i in {1..10}; do
    if docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 数据库已就绪${NC}"
        break
    fi
    echo -e "${YELLOW}等待数据库启动... ($i/10)${NC}"
    sleep 2
done

# 检查数据库表
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
    echo -e "${YELLOW}初始化表结构...${NC}"
    if [ -f "./create_tables.sh" ]; then
        ./create_tables.sh
    fi
fi

# 启动应用服务
echo -e "${YELLOW}启动后端和前端服务...${NC}"
docker-compose -f docker-compose.dev.yml up -d backend frontend
sleep 15

echo -e "${GREEN}✓ 开发环境启动完成！${NC}"
echo ""
docker-compose -f docker-compose.dev.yml ps

echo ""
echo -e "${GREEN}访问地址：${NC}"
echo "  前端：http://localhost:3000"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""
