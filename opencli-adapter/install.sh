#!/bin/bash
# 小说系统 opencli 适配器安装脚本
# 用法：./install-adapter.sh

set -e

ADAPTER_PATH="/Users/sanyi/.openclaw/workspace/novel_system/opencli-adapter"
OPENCLI_CONFIG="$HOME/.opencli/adapters.json"

echo "🦞 小说系统 opencli 适配器安装脚本"
echo "=================================="
echo ""

# 1. 验证适配器配置
echo "✅ 步骤 1: 验证适配器配置..."
if [ ! -f "$ADAPTER_PATH/manifest.json" ]; then
    echo "❌ 错误：manifest.json 不存在"
    exit 1
fi

# 验证 JSON 格式
if ! python3 -m json.tool "$ADAPTER_PATH/manifest.json" > /dev/null 2>&1; then
    echo "❌ 错误：manifest.json 格式不正确"
    exit 1
fi
echo "✅ manifest.json 验证通过"
echo ""

# 2. 测试 API 连接
echo "✅ 步骤 2: 测试 API 连接..."
API_URL="http://127.0.0.1:3000/api/v1/novels"
if curl -s "$API_URL" > /dev/null 2>&1; then
    echo "✅ API 连接成功：$API_URL"
    
    # 获取小说数量
    NOVEL_COUNT=$(curl -s "$API_URL" | python3 -c "import sys, json; print(json.load(sys.stdin).get('total', 0))" 2>/dev/null || echo "?")
    echo "📚 当前小说数量：$NOVEL_COUNT"
else
    echo "⚠️  API 暂时不可访问（可能服务未启动）"
    echo "   请确保小说系统在 http://127.0.0.1:3000 运行"
fi
echo ""

# 3. 创建/更新配置文件
echo "✅ 步骤 3: 配置 opencli..."
mkdir -p "$(dirname "$OPENCLI_CONFIG")"

# 检查是否已存在配置
if [ -f "$OPENCLI_CONFIG" ]; then
    echo "📝 备份现有配置..."
    cp "$OPENCLI_CONFIG" "$OPENCLI_CONFIG.bak"
fi

# 创建配置
cat > "$OPENCLI_CONFIG" << EOF
{
  "adapters": [
    {
      "name": "novel-system",
      "path": "$ADAPTER_PATH",
      "enabled": true
    }
  ]
}
EOF

echo "✅ 配置已保存到：$OPENCLI_CONFIG"
echo ""

# 4. 验证注册
echo "✅ 步骤 4: 验证注册..."
if command -v opencli &> /dev/null; then
    # 列出可用的 novel 命令
    echo "📋 可用的小说系统命令："
    opencli novel --help 2>/dev/null || echo "   提示：可能需要重启终端或运行 'opencli refresh'"
else
    echo "⚠️  opencli 未安装或未在 PATH 中"
fi
echo ""

# 5. 显示使用说明
echo "=================================="
echo "🎉 安装完成！"
echo "=================================="
echo ""
echo "📖 使用方法："
echo ""
echo "  # 列出所有小说"
echo "  opencli novel list"
echo ""
echo "  # 获取小说详情"
echo "  opencli novel get <novel_id>"
echo ""
echo "  # 创建新小说"
echo "  opencli novel create --title '我的小说' --genre '玄幻'"
echo ""
echo "  # AI 生成章节"
echo "  opencli novel generate <novel_id> <chapter> --outline '大纲'"
echo ""
echo "  # 查看更多命令"
echo "  opencli novel --help"
echo ""
echo "=================================="
echo ""

# 6. 可选：刷新 opencli
if command -v opencli &> /dev/null; then
    echo "💡 提示：如果命令不生效，尝试运行："
    echo "   opencli verify"
    echo ""
fi

echo "✅ 安装完成！"
