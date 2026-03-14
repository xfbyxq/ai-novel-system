#!/bin/bash

# 开发环境快速启动脚本
# 用法：./start_dev.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "开发环境启动 - 代码热更新模式"
echo "============================================================"
echo ""

# 检查是否已有容器运行
if docker ps | grep -q novel_backend; then
    echo -e "${YELLOW}检测到开发环境已在运行...${NC}"
    echo -e "${BLUE}停止现有服务...${NC}"
    docker-compose -f docker-compose.dev.yml down
    echo ""
fi

# 启动服务
echo -e "${YELLOW}[1/3] 启动基础服务（PostgreSQL, Redis）...${NC}"
docker-compose -f docker-compose.dev.yml up -d postgres redis
echo -e "${BLUE}等待数据库启动...${NC}"
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
echo ""

# 检查数据库表
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')

if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
    echo -e "${YELLOW}数据库为空，初始化表结构...${NC}"
    if [ -f "./create_tables.sh" ]; then
        ./create_tables.sh
    fi
fi

echo ""
echo -e "${YELLOW}[2/3] 启动后端服务（代码热更新）...${NC}"
docker-compose -f docker-compose.dev.yml up -d backend
echo -e "${BLUE}等待后端启动...${NC}"
sleep 10

# 检查后端日志
if docker logs novel_backend 2>&1 | grep -q "Application startup complete"; then
    echo -e "${GREEN}✓ 后端服务启动成功${NC}"
else
    echo -e "${YELLOW}后端服务启动中，请查看日志...${NC}"
fi

echo ""
echo -e "${YELLOW}[3/3] 启动前端服务（代码热更新）...${NC}"
docker-compose -f docker-compose.dev.yml up -d frontend
echo -e "${BLUE}等待前端启动...${NC}"
sleep 15

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ 开发环境启动完成！${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${CYAN}访问地址：${NC}"
echo "  前端开发服务器：http://localhost:3000"
echo "  后端 API 服务器：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""
echo -e "${CYAN}代码热更新：${NC}"
echo "  ✓ 修改后端代码后自动重启（uvicorn --reload）"
echo "  ✓ 修改前端代码后自动刷新（Vite HMR）"
echo ""
echo -e "${CYAN}查看日志：${NC}"
echo "  docker-compose -f docker-compose.dev.yml logs -f backend"
echo "  docker-compose -f docker-compose.dev.yml logs -f frontend"
echo ""
echo -e "${YELLOW}停止服务：${NC}"
echo "  docker-compose -f docker-compose.dev.yml down"
echo ""
echo -e "${YELLOW}重启单个服务：${NC}"
echo "  docker-compose -f docker-compose.dev.yml restart backend"
echo "  docker-compose -f docker-compose.dev.yml restart frontend"
echo ""

# 显示服务状态
echo -e "${CYAN}服务状态：${NC}"
docker-compose -f docker-compose.dev.yml ps
