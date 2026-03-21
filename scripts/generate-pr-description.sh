#!/bin/bash

# generate-pr-description.sh
# AI 自动生成 Pull Request 描述

set -e

echo "🤖 开始生成 AI PR 描述..."
echo "======================================"

# 配置
TARGET_BRANCH="${1:-main}"
OUTPUT_FILE="${2:-PR_DESCRIPTION.md}"

# 获取当前分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "当前分支：$CURRENT_BRANCH"
echo "目标分支：$TARGET_BRANCH"
echo ""

# ========== 步骤 1: 获取 commit 历史 ==========
echo "📦 步骤 1: 获取 commit 历史..."

commits=$(git log --oneline $TARGET_BRANCH..$CURRENT_BRANCH 2>/dev/null)

if [ -z "$commits" ]; then
    echo "❌ 没有找到与 $TARGET_BRANCH 的差异"
    exit 1
fi

commit_count=$(echo "$commits" | wc -l | tr -d ' ')
echo "找到 $commit_count 个提交"
echo ""

# ========== 步骤 2: 获取文件变更统计 ==========
echo "📄 步骤 2: 获取文件变更统计..."

files_changed=$(git diff --stat $TARGET_BRANCH..$CURRENT_BRANCH | tail -1)
insertions=$(git diff --stat $TARGET_BRANCH..$CURRENT_BRANCH | grep -oP '\d+(?= insertion)' || echo "0")
deletions=$(git diff --stat $TARGET_BRANCH..$CURRENT_BRANCH | grep -oP '\d+(?= deletion)' || echo "0")

echo "变更统计：$files_changed"
echo ""

# ========== 步骤 3: 获取详细的文件变更列表 ==========
echo "📝 步骤 3: 获取详细的文件变更列表..."

changed_files=$(git diff --name-only $TARGET_BRANCH..$CURRENT_BRANCH)

# 按目录分类
backend_files=$(echo "$changed_files" | grep -E "^backend/" || true)
frontend_files=$(echo "$changed_files" | grep -E "^frontend/" || true)
scripts_files=$(echo "$changed_files" | grep -E "^scripts/" || true)
docs_files=$(echo "$changed_files" | grep -E "^docs/" || true)
config_files=$(echo "$changed_files" | grep -E "(\.yml|\.yaml|\.toml|\.ini)$" || true)
test_files=$(echo "$changed_files" | grep -E "(test_|_test\.|\.spec\.)" || true)

echo "  后端文件：$(echo "$backend_files" | grep -c . || echo 0)"
echo "  前端文件：$(echo "$frontend_files" | grep -c . || echo 0)"
echo "  脚本文件：$(echo "$scripts_files" | grep -c . || echo 0)"
echo "  文档文件：$(echo "$docs_files" | grep -c . || echo 0)"
echo "  配置文件：$(echo "$config_files" | grep -c . || echo 0)"
echo "  测试文件：$(echo "$test_files" | grep -c . || echo 0)"
echo ""

# ========== 步骤 4: AI 生成 PR 描述 ==========
echo "🤖 步骤 4: AI 生成 PR 描述..."

# 准备上下文
cat > /tmp/pr-context.txt <<EOF
当前分支：$CURRENT_BRANCH
目标分支：$TARGET_BRANCH
提交数量：$commit_count
变更统计：$files_changed
插入行数：$insertions
删除行数：$deletions

提交历史:
$commits

变更的文件:
$changed_files

后端文件:
$backend_files

前端文件:
$frontend_files

脚本文件:
$scripts_files

文档文件:
$docs_files
EOF

# 调用 AI 生成 PR 描述（使用 OpenCode）
if command -v opencode &> /dev/null; then
    echo "  使用 OpenCode 生成..."
    
    opencode ask \
        --prompt "
根据以下 git 变更信息，生成一个专业的 Pull Request 描述（Markdown 格式）：

$(cat /tmp/pr-context.txt)

要求：
1. 标题简洁明了（使用 Conventional Commits 规范）
2. 包含变更内容摘要（3-5 个要点）
3. 说明影响范围（前端/后端/文档/测试等）
4. 列出关键变更（重要功能或修复）
5. 测试情况说明
6. 如果有 breaking changes，需要特别说明
7. 关联相关的 Issues（如果有）

输出格式：
\`\`\`markdown
## 📋 变更内容

## 🎯 影响范围

## 🔑 关键变更

## ✅ 测试情况

## ⚠️ 注意事项
\`\`\`
" \
        --output "$OUTPUT_FILE"
else
    echo "  ⚠️ OpenCode 未安装，使用模板生成..."
    
    # 使用模板生成
    cat > "$OUTPUT_FILE" <<EOF
## 📋 变更内容

- 提交数量：$commit_count 个
- 文件变更：$files_changed
- 新增代码：$insertions 行
- 删除代码：$deletions 行

### 提交历史
$(echo "$commits" | sed 's/^/- /')

## 🎯 影响范围

$(if [ -n "$backend_files" ]; then echo "- ✅ 后端：$(echo "$backend_files" | wc -l | tr -d ' ') 个文件"; fi)
$(if [ -n "$frontend_files" ]; then echo "- 🎨 前端：$(echo "$frontend_files" | wc -l | tr -d ' ') 个文件"; fi)
$(if [ -n "$scripts_files" ]; then echo "- 🔧 脚本：$(echo "$scripts_files" | wc -l | tr -d ' ') 个文件"; fi)
$(if [ -n "$docs_files" ]; then echo "- 📖 文档：$(echo "$docs_files" | wc -l | tr -d ' ') 个文件"; fi)
$(if [ -n "$test_files" ]; then echo "- 🧪 测试：$(echo "$test_files" | wc -l | tr -d ' ') 个文件"; fi)

## 🔑 关键变更

（待补充：请手动添加重要功能或修复的详细说明）

## ✅ 测试情况

- [ ] 单元测试已添加/更新
- [ ] 集成测试已验证
- [ ] 手动测试已完成
- [ ] 文档已更新

## ⚠️ 注意事项

（待补充：如果有 breaking changes 或需要特别注意的地方）

---

*此 PR 描述由 AI 辅助生成，请人工审核补充*
EOF
fi

echo ""
echo "✅ PR 描述已生成：$OUTPUT_FILE"
echo ""

# ========== 步骤 5: 显示预览 ==========
echo "📋 PR 描述预览:"
echo "======================================"
cat "$OUTPUT_FILE"
echo "======================================"
echo ""

# ========== 步骤 6: 提供下一步建议 ==========
echo "💡 下一步建议:"
echo ""
echo "1. 编辑完善 PR 描述："
echo "   code $OUTPUT_FILE"
echo ""
echo "2. 创建 GitHub PR："
echo "   gh pr create --title \"$(head -1 $OUTPUT_FILE | sed 's/^# //')\" --body-file $OUTPUT_FILE"
echo ""
echo "3. 或者手动在 GitHub 上创建："
echo "   https://github.com/xfbyxq/ai-novel-system/compare/$TARGET_BRANCH...$CURRENT_BRANCH"
echo ""
