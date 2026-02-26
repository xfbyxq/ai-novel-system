#!/bin/sh

# 启动脚本 - 确保环境变量在 Vite 启动时可用

# 输出环境变量用于调试
echo "🔍 Environment variables:"
echo "API_PROXY_TARGET: $API_PROXY_TARGET"

# 启动 Vite 开发服务器
exec npm run dev -- --host 0.0.0.0
