#!/bin/bash
# 测试小说系统 opencli 适配器
# 用法：./test-adapter.sh

set -e

API_BASE="http://127.0.0.1:3000/api/v1"
NOVEL_ID="bad753b6-abe7-495c-b713-de5c2ba5ed8c"

echo "🧪 小说系统 opencli 适配器测试"
echo "================================"
echo ""

# 测试 1：列出小说
echo "📋 测试 1: 列出所有小说..."
RESPONSE=$(curl -s "$API_BASE/novels")
TOTAL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))")
if [ "$TOTAL" -gt 0 ]; then
    echo "✅ 通过 - 小说数量：$TOTAL"
else
    echo "❌ 失败 - 没有小说"
fi
echo ""

# 测试 2：获取小说详情
echo "📖 测试 2: 获取小说详情..."
RESPONSE=$(curl -s "$API_BASE/novels/$NOVEL_ID")
TITLE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('title', '未知'))")
if [ "$TITLE" != "未知" ]; then
    echo "✅ 通过 - 小说标题：$TITLE"
else
    echo "❌ 失败 - 无法获取小说详情"
fi
echo ""

# 测试 3：获取章节列表
echo "📚 测试 3: 获取章节列表..."
RESPONSE=$(curl -s "$API_BASE/novels/$NOVEL_ID/chapters")
CHAPTER_COUNT=$(echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('items', [])))")
if [ "$CHAPTER_COUNT" -gt 0 ]; then
    echo "✅ 通过 - 章节数量：$CHAPTER_COUNT"
else
    echo "⚠️  警告 - 没有章节"
fi
echo ""

# 测试 4：获取角色列表
echo "👥 测试 4: 获取角色列表..."
RESPONSE=$(curl -s "$API_BASE/novels/$NOVEL_ID/characters")
if echo "$RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    echo "✅ 通过 - 角色列表可访问"
else
    echo "⚠️  警告 - 角色列表格式可能有误"
fi
echo ""

# 测试 5：获取小说统计
echo "📊 测试 5: 获取小说统计..."
RESPONSE=$(curl -s "$API_BASE/novels/$NOVEL_ID/stats")
if echo "$RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    echo "✅ 通过 - 统计数据可访问"
else
    echo "⚠️  警告 - 统计数据格式可能有误"
fi
echo ""

# 总结
echo "================================"
echo "📊 测试结果汇总"
echo "================================"
echo ""
echo "API 端点：$API_BASE"
echo "测试小说：$NOVEL_ID"
echo ""
echo "✅ 所有测试完成！"
echo ""
