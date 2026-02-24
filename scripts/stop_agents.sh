#!/bin/bash
"""Agent停止脚本"""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="$LOG_DIR/agent.pid"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "❌ 未找到Agent进程PID文件"
    echo "📄 文件路径: $PID_FILE"
    echo "💡 Agent系统可能未运行"
    exit 1
fi

# 读取PID
AGENT_PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p "$AGENT_PID" > /dev/null 2>&1; then
    echo "❌ Agent进程不存在"
    echo "🆔 进程ID: $AGENT_PID"
    echo "💡 可能已经停止或崩溃"
    rm -f "$PID_FILE"
    exit 1
fi

echo "🛑 停止Agent系统..."
echo "🆔 进程ID: $AGENT_PID"
echo "📋 停止时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "====================================="

# 发送SIGTERM信号
echo "📢 发送停止信号..."
kill -SIGTERM "$AGENT_PID"

# 等待进程退出
MAX_WAIT=30
WAIT_COUNT=0

while ps -p "$AGENT_PID" > /dev/null 2>&1 && [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    echo "⏳ 等待Agent系统停止... ($WAIT_COUNT/$MAX_WAIT)"
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

# 检查进程是否仍然存在
if ps -p "$AGENT_PID" > /dev/null 2>&1; then
    echo "⚠️  Agent系统未正常停止，强制终止..."
    kill -SIGKILL "$AGENT_PID"
    sleep 2
fi

# 清理PID文件
rm -f "$PID_FILE"

echo "✅ Agent系统已停止"
echo "📋 完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "====================================="
