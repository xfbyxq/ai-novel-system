#!/bin/bash

# 小说生成系统 Docker 停止脚本

echo "🛑 停止 Docker 容器..."

# 停止所有服务
docker-compose down

echo "✅ 所有服务已停止"

# 可选：清理未使用的镜像和容器
read -p "是否清理未使用的 Docker 资源？(y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 清理未使用的资源..."
    docker system prune -f
    echo "✅ 清理完成"
fi
