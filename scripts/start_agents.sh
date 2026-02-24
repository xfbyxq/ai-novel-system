#!/bin/bash
"""Agent启动脚本"""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
SCRIPT_DIR="$PROJECT_ROOT/scripts"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 启动Agent系统
echo "🚀 启动Agent系统..."
echo "📁 项目根目录: $PROJECT_ROOT"
echo "📋 启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "====================================="

# 使用poetry运行Python脚本
poetry run python "$SCRIPT_DIR/start_agents.py" > "$LOG_DIR/agent_startup.log" 2>&1 &

# 获取进程ID
AGENT_PID=$!

# 保存PID到文件
echo $AGENT_PID > "$LOG_DIR/agent.pid"

echo "✅ Agent系统已启动"
echo "🆔 进程ID: $AGENT_PID"
echo "📄 日志文件: $LOG_DIR/agent_system.log"
echo "📊 启动日志: $LOG_DIR/agent_startup.log"
echo "====================================="
echo "💡 查看运行状态: tail -f $LOG_DIR/agent_system.log"
echo "💡 停止Agent系统: $SCRIPT_DIR/stop_agents.sh"
echo "====================================="
