#!/bin/bash

# 小说生成系统 - Docker 快速部署脚本
# 用法：./deploy_docker.sh

set -e

echo "============================================================"
echo "小说生成系统 - Docker 快速部署"
echo "============================================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 步骤 1: 停止旧容器
echo -e "${YELLOW}[1/4] 停止旧容器...${NC}"
docker-compose down

# 步骤 2: 构建镜像（使用缓存）
echo -e "${YELLOW}[2/4] 构建镜像...${NC}"
docker-compose build

# 步骤 3: 启动服务
echo -e "${YELLOW}[3/4] 启动服务...${NC}"
docker-compose up -d

# 等待服务启动
echo ""
echo -e "${YELLOW}[4/4] 等待服务启动...${NC}"
sleep 10

# 检查服务状态
echo ""
echo -e "${GREEN}服务状态：${NC}"
docker-compose ps

echo ""
echo "============================================================"
echo -e "${GREEN}部署完成！${NC}"
echo "============================================================"
echo ""
echo "访问地址："
echo "  - 前端：http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档：http://localhost:8000/docs"
echo ""
