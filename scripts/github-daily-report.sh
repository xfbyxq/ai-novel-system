#!/bin/bash
# GitHub 自动化报告 - 每日生成
# 用法：./github-daily-report.sh [--send-feishu]

set -e

PROJECT_DIR="/Users/sanyi/.openclaw/workspace/novel_system"
REPORT_FILE="${PROJECT_DIR}/reports/github-daily-$(date +%Y-%m-%d).md"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

cd "$PROJECT_DIR"

# 创建报告目录
mkdir -p reports

# 生成报告
cat > "$REPORT_FILE" << EOF
# 🦞 OpenClaw GitHub 日报

**生成时间**: ${TIMESTAMP}
**仓库**: xfbyxq/ai-novel-system
**分支**: v2.0.0-release

---

## 📊 仓库统计

EOF

# 获取 Issues 统计
echo "### Issues 统计" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

OPEN_COUNT=$(opencli gh issue list --state open 2>/dev/null | wc -l | tr -d ' ')
CLOSED_COUNT=$(opencli gh issue list --state closed 2>/dev/null | wc -l | tr -d ' ')
TOTAL=$((OPEN_COUNT + CLOSED_COUNT))

echo "- **开放 Issues**: ${OPEN_COUNT}" >> "$REPORT_FILE"
echo "- **已关闭 Issues**: ${CLOSED_COUNT}" >> "$REPORT_FILE"
echo "- **总计**: ${TOTAL}" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 获取开放 Issues 列表
echo "### 🔴 开放的 Issues" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| # | 标题 | 标签 | 创建时间 |" >> "$REPORT_FILE"
echo "|---|------|------|----------|" >> "$REPORT_FILE"

opencli gh issue list --limit 20 --state open 2>/dev/null | while IFS=$'\t' read -r number title labels created_at; do
    echo "| #${number} | ${title} | ${labels} | ${created_at} |" >> "$REPORT_FILE"
done

echo "" >> "$REPORT_FILE"

# 获取今日关闭的 Issues
echo "### ✅ 今日关闭的 Issues" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| # | 标题 | 关闭时间 |" >> "$REPORT_FILE"
echo "|---|------|----------|" >> "$REPORT_FILE"

opencli gh issue list --limit 20 --state closed 2>/dev/null | while IFS=$'\t' read -r number title labels closed_at; do
    echo "| #${number} | ${title} | ${closed_at} |" >> "$REPORT_FILE"
done

echo "" >> "$REPORT_FILE"

# 获取最近 Commits
echo "### 📝 最近的 Commits" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Commit | 信息 | 时间 |" >> "$REPORT_FILE"
echo "|--------|------|------|" >> "$REPORT_FILE"

git log --oneline -10 --format="%h|%s|%ar" 2>/dev/null | while IFS='|' read -r hash msg time; do
    echo "| \`${hash}\` | ${msg} | ${time} |" >> "$REPORT_FILE"
done

echo "" >> "$REPORT_FILE"

# 分支状态
echo "### 🌿 分支状态" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "\`\`\`" >> "$REPORT_FILE"
git branch -a 2>/dev/null | head -20 >> "$REPORT_FILE"
echo "\`\`\`" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "✅ GitHub 日报已生成：${REPORT_FILE}"

# 如果指定 --send-feishu，发送到飞书
if [[ "$1" == "--send-feishu" ]]; then
    echo "📤 发送到飞书..."
    # TODO: 集成飞书 API
fi

# 显示报告
echo ""
echo "📋 报告预览："
echo "============"
cat "$REPORT_FILE"
