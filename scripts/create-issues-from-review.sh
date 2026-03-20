#!/bin/bash

# create-issues-from-review.sh
# 从 OpenCode 审查报告创建 GitHub Issues

set -e

REVIEW_REPORT="${1:-review-report.md}"

if [ ! -f "$REVIEW_REPORT" ]; then
    echo "❌ 审查报告不存在：$REVIEW_REPORT"
    exit 1
fi

echo "📋 开始从审查报告创建 GitHub Issues..."
echo "报告文件：$REVIEW_REPORT"

# 检查 gh CLI 是否已认证
if ! gh auth status &> /dev/null; then
    echo "❌ GitHub CLI 未认证，请先运行：gh auth login"
    exit 1
fi

# 解析审查报告，提取问题
# 假设报告格式：
# ### 🔴 高优先级问题
# | 文件 | 问题 | 建议修复方案 |

# 提取高优先级问题
echo ""
echo "🔴 处理高优先级问题..."
grep -A 100 "### 🔴 高优先级问题" "$REVIEW_REPORT" | \
  grep -B 100 "### 🟡 中优先级问题" | \
  head -n -1 | \
  tail -n +2 | \
  while IFS='|' read -r file problem solution; do
    # 清理数据
    file=$(echo "$file" | xargs)
    problem=$(echo "$problem" | xargs)
    solution=$(echo "$solution" | xargs)
    
    # 跳过表头
    if [[ "$file" == "文件" ]] || [[ -z "$file" ]]; then
      continue
    fi
    
    echo "  创建 Issue: $problem"
    
    # 创建 Issue
    gh issue create \
      --title "🔴 [高优先级] $problem" \
      --body "
## 问题描述
$problem

## 文件位置
- \`$file\`

## 修复方案
$solution

## 优先级
🔴 高优先级

## 关联
- 关联代码审查报告：$REVIEW_REPORT
- 自动生成时间：$(date -u +"%Y-%m-%d %H:%M:%S UTC")
" \
      --label "bug,high-priority,auto-generated" \
      --assignee "@me"
    
    echo "  ✅ Issue 创建成功"
  done

# 提取中优先级问题
echo ""
echo "🟡 处理中优先级问题..."
grep -A 100 "### 🟡 中优先级问题" "$REVIEW_REPORT" | \
  grep -B 100 "### 🟢 低优先级问题" | \
  head -n -1 | \
  tail -n +2 | \
  while IFS='|' read -r file problem solution; do
    file=$(echo "$file" | xargs)
    problem=$(echo "$problem" | xargs)
    solution=$(echo "$solution" | xargs)
    
    if [[ "$file" == "文件" ]] || [[ -z "$file" ]]; then
      continue
    fi
    
    echo "  创建 Issue: $problem"
    
    gh issue create \
      --title "🟡 [中优先级] $problem" \
      --body "
## 问题描述
$problem

## 文件位置
- \`$file\`

## 修复方案
$solution

## 优先级
🟡 中优先级

## 关联
- 关联代码审查报告：$REVIEW_REPORT
- 自动生成时间：$(date -u +"%Y-%m-%d %H:%M:%S UTC")
" \
      --label "enhancement,medium-priority,auto-generated"
    
    echo "  ✅ Issue 创建成功"
  done

# 提取低优先级问题
echo ""
echo "🟢 处理低优先级问题..."
grep -A 100 "### 🟢 低优先级问题" "$REVIEW_REPORT" | \
  tail -n +2 | \
  while IFS='|' read -r file problem solution; do
    file=$(echo "$file" | xargs)
    problem=$(echo "$problem" | xargs)
    solution=$(echo "$solution" | xargs)
    
    if [[ "$file" == "文件" ]] || [[ -z "$file" ]]; then
      continue
    fi
    
    echo "  创建 Issue: $problem"
    
    gh issue create \
      --title "🟢 [低优先级] $problem" \
      --body "
## 问题描述
$problem

## 文件位置
- \`$file\`

## 修复方案
$solution

## 优先级
🟢 低优先级

## 关联
- 关联代码审查报告：$REVIEW_REPORT
- 自动生成时间：$(date -u +"%Y-%m-%d %H:%M:%S UTC")
" \
      --label "enhancement,low-priority,auto-generated"
    
    echo "  ✅ Issue 创建成功"
  done

echo ""
echo "✅ 所有 Issues 创建完成！"
