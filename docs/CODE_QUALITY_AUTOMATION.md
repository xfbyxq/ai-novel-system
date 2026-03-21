# 🤖 代码质量自动化系统

本文档说明如何配置和使用自动化代码质量改进系统。

---

## 📋 系统概述

### 核心流程

```
代码提交 → 自动审查 → 创建 Issues → 自动修复 → 验证评分 → 提交 PR
```

### 组件说明

| 组件 | 说明 | 位置 |
|------|------|------|
| **GitHub Actions** | CI/CD 自动化工作流 | `.github/workflows/code-quality.yml` |
| **审查脚本** | 从审查报告创建 Issues | `scripts/create-issues-from-review.sh` |
| **评分脚本** | 计算综合质量评分 | `scripts/quality-score.sh` |
| **修复脚本** | 本地自动化修复 | `scripts/auto-review-fix.sh` |

---

## 🚀 快速开始

### 前置要求

1. **GitHub CLI** 已安装并认证
   ```bash
   gh auth login
   ```

2. **OpenCode CLI** 已安装
   ```bash
   pip install opencode-cli
   ```

3. **Python 工具** 已安装
   ```bash
   pip install pylint mypy black isort pytest coverage
   ```

### 配置 GitHub Actions

1. **启用工作流**
   - 访问：https://github.com/xfbyxq/ai-novel-system/actions
   - 点击 "I understand my workflows, go ahead and enable them"

2. **配置 Secrets**（如需）
   - Settings → Secrets and variables → Actions
   - 添加必要的 API keys

3. **测试工作流**
   - Actions → Code Quality Automation → Run workflow
   - 选择分支，点击 "Run workflow"

---

## 📖 使用方式

### 方式 A：GitHub Actions（推荐）

工作流会自动在以下情况触发：

- ✅ Push 到 main/develop 分支
- ✅ 创建 Pull Request
- ✅ 每天 UTC 2:00（北京时间 10:00）
- ✅ 手动触发

**查看执行结果**：
https://github.com/xfbyxq/ai-novel-system/actions

### 方式 B：本地执行

```bash
cd /Users/sanyi/.openclaw/workspace/novel_system

# 运行完整自动化流程
./scripts/auto-review-fix.sh

# 或分步骤执行

# 1. 代码审查
opencode review --output review-report.md

# 2. 创建 Issues
./scripts/create-issues-from-review.sh review-report.md

# 3. 质量验证
./scripts/quality-score.sh
```

---

## ⚙️ 配置选项

### 质量阈值

编辑 `.github/workflows/code-quality.yml`:

```yaml
env:
  QUALITY_THRESHOLD: 90  # 修改目标评分
```

### 触发时间

编辑 cron 表达式（UTC 时间）:

```yaml
schedule:
  - cron: '0 2 * * *'  # 每天 2:00 UTC
```

改为北京时间 2:00:
```yaml
schedule:
  - cron: '0 18 * * *'  # 18:00 UTC = 北京时间 2:00
```

### 修复迭代次数

编辑 `scripts/auto-review-fix.sh`:

```bash
MAX_ITERATIONS=3  # 最大修复迭代次数
```

---

## 📊 质量评分计算

综合评分 = 代码审查 (50%) + Pylint (20%) + 测试覆盖率 (30%)

```bash
# 查看当前评分
./scripts/quality-score.sh
```

**示例输出**:
```
========== 质量评分报告 ==========
代码审查评分：  75.0 (权重：0.5)
Pylint 评分：    80.0 (权重：0.2)
测试覆盖率：    65% (权重：0.3)
--------------------------------
**综合评分**:    76.00 / 100
================================
❌ 质量评分未达标 (76.00 < 90)
```

---

## 🔧 故障排查

### GitHub Actions 失败

**问题**: 工作流未触发

**解决**:
1. 检查 `.github/workflows/code-quality.yml` 语法
2. 确认工作流已启用
3. 查看 Actions 标签页的错误日志

**问题**: gh CLI 认证失败

**解决**:
```bash
# 重新认证
gh auth logout
gh auth login --web
```

### 本地脚本失败

**问题**: 权限不足

**解决**:
```bash
chmod +x scripts/*.sh
```

**问题**: 依赖未安装

**解决**:
```bash
pip install opencode-cli pylint pytest coverage
```

---

## 📈 监控与改进

### 查看历史评分

```bash
# 查看最近的审查报告
ls -lt review-report*.md | head -5
```

### 追踪 Issues 状态

```bash
# 查看自动创建的 Issues
gh issue list --label auto-generated
```

### 分析趋势

访问 GitHub Insights:
https://github.com/xfbyxq/ai-novel-system/pulse

---

## 🎯 最佳实践

1. **定期运行**: 每天至少执行一次自动化审查
2. **及时修复**: 优先处理高优先级问题
3. **代码审查**: 自动修复后仍需人工 review
4. **测试覆盖**: 保持测试覆盖率 > 70%
5. **渐进改进**: 不要一次性修复所有问题

---

## 📚 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [OpenCode CLI 文档](https://opencode.ai/docs)
- [Pylint 用户指南](https://pylint.pycqa.org/)
- [Code Climate 最佳实践](https://codeclimate.com/best-practices/)

---

## 🤝 贡献

欢迎提交 Issue 和 PR 改进此自动化系统！

---

*最后更新：2026-03-20*
