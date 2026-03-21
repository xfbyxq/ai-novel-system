#!/bin/bash

# quality-score.sh
# 计算代码质量综合评分

set -e

echo "📊 计算代码质量综合评分..."

# 配置权重
REVIEW_WEIGHT=0.5
PYLINT_WEIGHT=0.2
COVERAGE_WEIGHT=0.3

# 质量阈值
THRESHOLD=90

# ========== 1. 代码审查评分 ==========
echo ""
echo "1️⃣ 代码审查评分..."
if [ -f "review-report.md" ]; then
    review_score=$(grep -oP '代码质量评分：\K[0-9.]+' review-report.md 2>/dev/null || echo "0")
else
    echo "  ⚠️ 未找到审查报告，使用默认值 70"
    review_score=70
fi
echo "  评分：$review_score"

# ========== 2. Pylint 静态分析 ==========
echo ""
echo "2️⃣ Pylint 静态分析..."
if command -v pylint &> /dev/null; then
    pylint backend/ --output-format=text > /tmp/pylint-report.txt 2>&1 || true
    pylint_score=$(grep -oP 'rated at \K[0-9.]+' /tmp/pylint-report.txt 2>/dev/null || echo "0")
    echo "  评分：$pylint_score"
else
    echo "  ⚠️ Pylint 未安装，使用默认值 70"
    pylint_score=70
fi

# ========== 3. 测试覆盖率 ==========
echo ""
echo "3️⃣ 测试覆盖率..."
if command -v pytest &> /dev/null && command -v coverage &> /dev/null; then
    coverage run -m pytest backend/tests/ -q > /dev/null 2>&1 || true
    coverage report > /tmp/coverage-report.txt
    coverage=$(grep "TOTAL" /tmp/coverage-report.txt | awk '{print $NF}' | tr -d '%')
    echo "  覆盖率：$coverage%"
else
    echo "  ⚠️ 测试工具未安装，使用默认值 60"
    coverage=60
fi

# ========== 4. 计算综合评分 ==========
echo ""
echo "📈 计算综合评分..."

composite_score=$(echo "scale=2; $review_score * $REVIEW_WEIGHT + $pylint_score * $PYLINT_WEIGHT + $coverage * $COVERAGE_WEIGHT" | bc)

echo ""
echo "========== 质量评分报告 =========="
echo "代码审查评分：  $review_score (权重：$REVIEW_WEIGHT)"
echo "Pylint 评分：    $pylint_score (权重：$PYLINT_WEIGHT)"
echo "测试覆盖率：    $coverage% (权重：$COVERAGE_WEIGHT)"
echo "--------------------------------"
echo "**综合评分**:    $composite_score / 100"
echo "================================"

# ========== 5. 判断是否达标 ==========
echo ""
if (( $(echo "$composite_score >= $THRESHOLD" | bc -l) )); then
    echo "✅ 质量评分达标！($composite_score >= $THRESHOLD)"
    exit 0
else
    echo "❌ 质量评分未达标 ($composite_score < $THRESHOLD)"
    echo "   需要继续改进代码质量"
    exit 1
fi
