#!/bin/bash

# 小说生成系统 Docker 部署启动脚本

echo "🚀 开始构建并启动 Docker 容器..."

# 停止现有容器
echo "📦 停止现有容器..."
docker-compose down

# 构建并启动所有服务
echo "🔨 构建镜像并启动服务..."
docker-compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "📊 服务状态："
docker-compose ps

# 检查后端健康状态
echo ""
echo "🔍 检查后端健康状态..."
curl -s http://localhost:8000/health | jq '.' || echo "后端服务未就绪"

# 显示日志
echo ""
echo "📝 查看服务日志（按 Ctrl+C 退出）："
docker-compose logs -f
