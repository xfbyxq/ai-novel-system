#!/bin/bash

# 小说生成系统 - Docker 启动脚本（带构建）
# 用法：./docker-start.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}停止现有容器...${NC}"
docker-compose down

echo -e "${YELLOW}构建并启动服务...${NC}"
docker-compose up -d --build

echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

echo -e "${GREEN}启动完成！${NC}"
echo ""
docker-compose ps

echo ""
echo -e "${GREEN}服务已启动：${NC}"
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
