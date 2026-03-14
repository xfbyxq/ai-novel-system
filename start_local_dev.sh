#!/bin/bash

# 本地开发模式启动脚本 - 不使用 Docker 打包
# 用法：./start_local_dev.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "本地开发模式 - 代码热更新"
echo "============================================================"
echo ""

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
echo ""

# 检查数据库表
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
if [ "$TABLE_COUNT" = "0" ] || [ -z "$TABLE_COUNT" ]; then
    echo -e "${YELLOW}初始化数据库表...${NC}"
    ./create_tables.sh
fi

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}后端服务 (本地运行)${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "${YELLOW}启动命令：${NC}"
echo "  cd /Users/sanyi/code/python/novel_system"
echo "  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo -e "${YELLOW}或者在新终端手动运行：${NC}"
echo "  source .venv/bin/activate  # 如果有虚拟环境"
echo "  uvicorn backend.main:app --reload"
echo ""

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}前端服务 (本地运行)${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "${YELLOW}启动命令：${NC}"
echo "  cd /Users/sanyi/code/python/novel_system/frontend"
echo "  npm run dev"
echo ""
echo -e "${YELLOW}或者在新终端手动运行：${NC}"
echo "  cd frontend"
echo "  npm run dev"
echo ""

echo ""
echo -e "${CYAN}访问地址：${NC}"
echo "  前端：http://localhost:3000"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""

echo -e "${YELLOW}提示：${NC}"
echo "  - 后端代码修改后自动重启 (uvicorn --reload)"
echo "  - 前端代码修改后自动刷新 (Vite HMR)"
echo "  - PostgreSQL 和 Redis 在 Docker 容器中运行"
echo "  - 数据库连接：localhost:5434 (novel_user/novel_pass)"
echo ""

# 提供一键启动选项
read -p "是否现在启动后端服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}启动后端服务...${NC}"
    cd /Users/sanyi/code/python/novel_system
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
fi
