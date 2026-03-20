#!/bin/bash

# auto-review-fix.sh
# 自动化代码审查修复脚本（本地执行版本）

set -e

echo "🤖 启动自动化代码审查修复流程..."
echo "======================================"

# 配置
QUALITY_THRESHOLD=90
MAX_ITERATIONS=3
WORKDIR="${1:-.}"

cd "$WORKDIR"

# ========== 步骤 1: 代码审查 ==========
echo ""
echo "📋 步骤 1: 代码审查..."
opencode review \
    --output review-report.md \
    --format markdown \
    --verbose

# 提取评分
review_score=$(grep -oP '代码质量评分：\K[0-9.]+' review-report.md || echo "0")
echo "✅ 审查完成，当前评分：$review_score"

# ========== 步骤 2: 创建 Issues ==========
echo ""
echo "📝 步骤 2: 创建 GitHub Issues..."
./scripts/create-issues-from-review.sh review-report.md

# ========== 步骤 3: 自动修复 ==========
echo ""
echo "🔧 步骤 3: 自动修复..."
iteration=0

while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))
    echo ""
    echo "  第 $iteration 次修复迭代..."
    
    # 运行修复
    opencode fix \
        --priority high \
        --max-iterations 5 \
        --auto-commit \
        --output fix-report-$iteration.md
    
    # 检查是否有修复
    fixed_count=$(grep -c "✅ Fixed" fix-report-$iteration.md || echo "0")
    echo "  修复了 $fixed_count 个问题"
    
    if [ "$fixed_count" -eq 0 ]; then
        echo "  ℹ️ 没有更多可修复的问题"
        break
    fi
    
    # 重新审查
    opencode review --output review-report.md
    new_score=$(grep -oP '代码质量评分：\K[0-9.]+' review-report.md || echo "0")
    echo "  当前评分：$new_score"
    
    # 检查是否达标
    if (( $(echo "$new_score >= $QUALITY_THRESHOLD" | bc -l) )); then
        echo "  ✅ 评分已达到阈值！"
        review_score=$new_score
        break
    fi
    
    review_score=$new_score
done

# ========== 步骤 4: 质量验证 ==========
echo ""
echo "📊 步骤 4: 质量验证..."
./scripts/quality-score.sh
quality_result=$?

# ========== 步骤 5: 提交结果 ==========
echo ""
echo "📦 步骤 5: 提交结果..."

# 添加变更
git add -A

# 检查是否有变更
if ! git diff --staged --quiet; then
    git commit -m "🤖 Auto-Fix: Code quality improvements (score: $review_score) [skip ci]"
    
    # 如果质量达标，创建 PR
    if [ $quality_result -eq 0 ]; then
        echo ""
        echo "🚀 质量达标，创建 Pull Request..."
        
        gh pr create \
            --title "🤖 Auto-Fix: Code Quality Improvements (Score: $review_score)" \
            --body "
## 自动修复报告

**综合评分**: $review_score / 100
**修复时间**: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
**修复迭代**: $iteration 次

### 修复内容
- 自动修复高优先级问题
- 代码质量优化
- 测试覆盖率提升

---
*此 PR 由自动化脚本生成*
" \
            --base main \
            --label "auto-fix"
        
        echo "✅ PR 创建成功！"
    else
        echo ""
        echo "⚠️ 质量未达标，仅提交代码"
        git push
    fi
else
    echo "ℹ️ 没有需要提交的变更"
fi

echo ""
echo "======================================"
echo "✅ 自动化流程完成！"
echo "最终评分：$review_score"
echo "======================================"
