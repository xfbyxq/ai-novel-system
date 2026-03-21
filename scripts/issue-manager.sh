#!/bin/bash
# GitHub Issue 管理自动化
# 用法：./issue-manager.sh [command] [options]

set -e

PROJECT_DIR="/Users/sanyi/.openclaw/workspace/novel_system"
cd "$PROJECT_DIR"

# 命令帮助
show_help() {
    cat << EOF
🦞 OpenClaw Issue 管理器

用法：./issue-manager.sh <command> [options]

命令:
  list [open|closed]     列出 Issues（默认：open）
  stats                  显示 Issue 统计
  today                  显示今日修复的 Issues
  assign <issue> <user>  分配 Issue
  close <issue>          关闭 Issue
  label <issue> <label>  添加标签
  search <query>         搜索 Issues
  report                 生成 Issue 报告

示例:
  ./issue-manager.sh list open
  ./issue-manager.sh stats
  ./issue-manager.sh today
  ./issue-manager.sh close 123
  ./issue-manager.sh search "bug"

EOF
}

# 列出 Issues
list_issues() {
    local state="${1:-open}"
    local limit="${2:-20}"
    
    # 首字母大写（兼容旧版 bash）
    local state_cap=$(echo "$state" | sed 's/\b\(.\)/\u\1/g')
    
    echo "📋 ${state_cap} Issues (limit: ${limit})"
    echo "================================"
    opencli gh issue list --state "$state" --limit "$limit"
}

# Issue 统计
show_stats() {
    echo "📊 Issue 统计"
    echo "=============="
    echo ""
    
    local open_count=$(opencli gh issue list --state open 2>/dev/null | wc -l | tr -d ' ')
    local closed_count=$(opencli gh issue list --state closed 2>/dev/null | wc -l | tr -d ' ')
    local total=$((open_count + closed_count))
    
    echo "开放 Issues:   ${open_count}"
    echo "已关闭 Issues: ${closed_count}"
    echo "总计：         ${total}"
    echo ""
    
    if [[ $total -gt 0 ]]; then
        local closed_rate=$((closed_count * 100 / total))
        echo "修复率：${closed_rate}%"
    fi
}

# 今日修复的 Issues
show_today() {
    echo "✅ 今日修复的 Issues"
    echo "===================="
    echo ""
    
    local today=$(date +%Y-%m-%d)
    echo "日期：${today}"
    echo ""
    
    opencli gh issue list --state closed --limit 20 | while IFS=$'\t' read -r number title labels closed_at; do
        if [[ "$closed_at" == *"$today"* ]]; then
            echo "#${number} ${title}"
        fi
    done
}

# 关闭 Issue
close_issue() {
    local issue="$1"
    echo "🔒 关闭 Issue #${issue}..."
    opencli gh issue close "$issue"
    echo "✅ Issue #${issue} 已关闭"
}

# 搜索 Issues
search_issues() {
    local query="$1"
    echo "🔍 搜索：${query}"
    echo "================"
    opencli gh search issues "$query" --limit 20
}

# 生成报告
generate_report() {
    echo "📊 Issue 报告"
    echo "=============="
    echo ""
    
    show_stats
    echo ""
    
    echo "🔴 开放的 Issues (前 10)"
    echo "-----------------------"
    list_issues open 10
    echo ""
    
    echo "✅ 最近关闭的 Issues (前 10)"
    echo "--------------------------"
    list_issues closed 10
}

# 主程序
case "${1:-help}" in
    list)
        list_issues "${2:-open}" "${3:-20}"
        ;;
    stats)
        show_stats
        ;;
    today)
        show_today
        ;;
    close)
        if [[ -z "$2" ]]; then
            echo "❌ 错误：请指定 Issue 编号"
            exit 1
        fi
        close_issue "$2"
        ;;
    search)
        if [[ -z "$2" ]]; then
            echo "❌ 错误：请指定搜索关键词"
            exit 1
        fi
        search_issues "$2"
        ;;
    report)
        generate_report
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ 未知命令：$1"
        show_help
        exit 1
        ;;
esac
