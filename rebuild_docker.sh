#!/bin/bash

# 小说生成系统 - Docker 重建脚本（无缓存）
# 用法：./rebuild_docker.sh

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}停止并清理旧容器...${NC}"
docker-compose down --remove-orphans

echo -e "${YELLOW}清理悬空镜像...${NC}"
docker image prune -f

echo -e "${YELLOW}重新构建所有镜像（无缓存）...${NC}"
docker-compose build --no-cache

echo -e "${YELLOW}启动所有服务...${NC}"
docker-compose up -d

echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

echo -e "${GREEN}Docker 重建完成！${NC}"
echo ""
docker-compose ps

echo ""
echo -e "${GREEN}服务已启动：${NC}"
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
echo ""
