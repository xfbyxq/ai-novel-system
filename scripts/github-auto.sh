#!/bin/bash
# GitHub 自动化脚本 - 使用 opencli 增强 GitHub 工作流
# 用法：./github-auto.sh

set -e

echo "🦞 OpenClaw GitHub 自动化报告"
echo "================================"
echo ""

# 1. 获取开放的 Issues
echo "📋 开放的 Issues（前 10 个）"
echo "----------------------------"
opencli gh issue list --limit 10 --state open
echo ""

# 2. 获取已关闭的 Issues（今日修复）
echo "✅ 今日修复的 Issues"
echo "--------------------"
opencli gh issue list --limit 10 --state closed
echo ""

# 3. 获取 GitHub 仓库统计
echo "📊 仓库统计"
echo "------------"
echo "开放 Issues: $(opencli gh issue list --state open 2>/dev/null | wc -l)"
echo "已关闭 Issues: $(opencli gh issue list --state closed 2>/dev/null | wc -l)"
echo ""

# 4. 获取最近的 Commits
echo "📝 最近的 Commits"
echo "----------------"
git log --oneline -10
echo ""

# 5. 检查分支状态
echo "🌿 分支状态"
echo "------------"
git branch -a
echo ""

# 6. 检查远程仓库
echo "🌐 远程仓库"
echo "------------"
git remote -v
echo ""

echo "✅ GitHub 自动化报告完成！"
