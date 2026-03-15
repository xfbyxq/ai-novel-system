#!/bin/bash

# 小说生成系统 - Docker 停止脚本
# 用法：./docker-stop.sh

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}停止 Docker 容器...${NC}"
docker-compose down
echo -e "${GREEN}✅ 所有服务已停止${NC}"

# 可选：清理未使用的镜像和容器
read -p "是否清理未使用的 Docker 资源？(y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🧹 清理未使用的资源...${NC}"
    docker system prune -f
    echo -e "${GREEN}✅ 清理完成${NC}"
fi
