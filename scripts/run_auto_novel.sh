#!/bin/bash
"""自动小说创作流程启动脚本"""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
SCRIPT_DIR="$PROJECT_ROOT/scripts"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 默认参数
GENRE="玄幻"
TAGS="系统,穿越"
PLATFORM="qidian"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--genre)
            GENRE="$2"
            shift 2
            ;;
        -t|--tags)
            TAGS="$2"
            shift 2
            ;;
        -p|--platform)
            PLATFORM="$2"
            shift 2
            ;;
        -h|--help)
            echo "📋 自动小说创作流程启动脚本"
            echo ""
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -g, --genre <类型>    设置小说类型 (默认: 玄幻)"
            echo "  -t, --tags <标签>      设置小说标签，用逗号分隔 (默认: 系统,穿越)"
            echo "  -p, --platform <平台>  设置发布平台 (默认: qidian)"
            echo "  -h, --help            显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0 -g 都市 -t 职场,言情 -p douyin"
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# 启动自动小说创作流程
echo "🚀 启动自动小说创作流程..."
echo "📋 配置:"
echo "   小说类型: $GENRE"
echo "   小说标签: $TAGS"
echo "   发布平台: $PLATFORM"
echo "📁 项目根目录: $PROJECT_ROOT"
echo "📋 启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "====================================="

# 将标签转换为Python列表格式
PYTHON_TAGS="[$(echo "$TAGS" | sed 's/,/", "/g' | sed 's/^/"/;s/$/"/')]"

# 使用poetry运行Python脚本
echo "🎯 开始完整小说创作流程..."
echo "====================================="

poetry run python -c "
import asyncio
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from scripts.auto_novel_process import AutoNovelProcess

async def main():
    process = AutoNovelProcess()
    await process.initialize()
    result = await process.run_full_process(
        genre='$GENRE',
        tags=$PYTHON_TAGS,
        platform='$PLATFORM'
    )
    return result

result = asyncio.run(main())
print('=====================================')
if result['success']:
    print('🎉 自动小说创作流程成功完成！')
    print(f'📋 完成时间: {result.get("completion_time", "N/A")}')
    print(f'💰 总token消耗: {result.get("cost", {}).get("total_tokens", "N/A")}')
    print(f'💰 总成本: ¥{result.get("cost", {}).get("total_cost", 0):.2f}')
    print('✅ 所有任务已完成:')
    for task_type, task_id in result.get('tasks', {}).items():
        print(f'   - {task_type}: {task_id}')
else:
    print('💥 自动小说创作流程失败')
    print(f'❌ 错误信息: {result.get("error", "Unknown error")}')
    if result.get('tasks'):
        print('⚠️  已执行的任务:')
        for task_type, task_id in result.get('tasks', {}).items():
            print(f'   - {task_type}: {task_id}')
print('=====================================')
" > "$LOG_DIR/auto_novel_output.log" 2>&1

# 显示输出
cat "$LOG_DIR/auto_novel_output.log"

echo "📄 详细日志: $LOG_DIR/auto_novel_process.log"
echo "====================================="
