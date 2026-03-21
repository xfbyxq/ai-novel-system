#!/bin/bash

# 小说生成系统 - Docker 快速部署脚本（使用缓存）
# 用法：./deploy_docker.sh

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}停止旧容器...${NC}"
docker-compose down

echo -e "${YELLOW}构建镜像（使用缓存）...${NC}"
docker-compose build

echo -e "${YELLOW}启动服务...${NC}"
docker-compose up -d

echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

echo -e "${GREEN}部署完成！${NC}"
echo ""
docker-compose ps

echo ""
echo -e "${GREEN}服务已启动：${NC}"
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
echo ""
