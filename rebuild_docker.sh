#!/bin/bash

# 小说生成系统 - Docker 重建和部署脚本
# 用法：./rebuild_docker.sh

set -e

echo "============================================================"
echo "小说生成系统 - Docker 重建和部署"
echo "============================================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 步骤 1: 停止并清理旧容器
echo -e "${YELLOW}[1/6] 停止并清理旧容器...${NC}"
docker-compose down --remove-orphans

# 步骤 2: 清理悬空镜像
echo -e "${YELLOW}[2/6] 清理悬空镜像...${NC}"
docker image prune -f

# 步骤 3: 重新构建所有镜像（无缓存）
echo -e "${YELLOW}[3/6] 重新构建所有镜像（无缓存）...${NC}"
docker-compose build --no-cache

# 步骤 4: 启动所有服务
echo -e "${YELLOW}[4/6] 启动所有服务...${NC}"
docker-compose up -d

# 等待服务启动
echo ""
echo -e "${YELLOW}[5/6] 等待服务启动...${NC}"
sleep 10

# 步骤 5: 检查服务状态
echo -e "${YELLOW}[6/6] 检查服务状态...${NC}"
echo ""
docker-compose ps

echo ""
echo "============================================================"
echo -e "${GREEN}Docker 重建和部署完成！${NC}"
echo "============================================================"
echo ""
echo "服务访问地址："
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
echo ""
echo "查看日志："
echo "  - 后端：docker-compose logs -f backend"
echo "  - 前端：docker-compose logs -f frontend"
echo "  - 数据库：docker-compose logs -f postgres"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
echo "重启服务："
echo "  docker-compose restart"
echo ""
