#!/bin/bash
# 批量创建 GitHub Issues 脚本
# 使用前请确保：gh auth login 已完成认证

set -e

cd "$(dirname "$0")/.."

echo "🚀 开始创建 GitHub Issues..."
echo ""

# Issue 1: 数据库密码硬编码
echo "📝 创建 Issue 1/16: 数据库密码硬编码"
gh issue create --title "🔴 数据库密码硬编码" --body "## 问题描述
数据库连接密码以明文形式硬编码在配置文件中，存在严重安全风险。

## 影响
- 🔴 **安全风险**：代码泄露会导致数据库密码暴露
- 攻击者可直接访问生产数据库
- 违反安全最佳实践

## 文件位置
- \`backend/config.py:30\`

## 修复方案
1. 使用环境变量存储数据库密码
2. 添加 .env 示例文件（.env.example）
3. 更新配置加载逻辑，从环境变量读取敏感信息
4. 确保 .env 已加入 .gitignore

## 预估时间
10 分钟

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "security,bug,priority-high"

# Issue 2: Redis 连接泄漏
echo "📝 创建 Issue 2/16: Redis 连接泄漏"
gh issue create --title "🔴 Redis 连接泄漏" --body "## 问题描述
Redis 客户端连接在使用后未正确关闭，导致连接泄漏。

## 影响
- 🔴 **性能问题**：连接池耗尽后服务不可用
- 内存泄漏风险
- 系统稳定性下降

## 文件位置
- \`backend/redis_client.py\`（3 处）

## 修复方案
1. 使用上下文管理器（with 语句）确保连接关闭
2. 添加连接池配置和监控
3. 实现连接超时和自动回收机制
4. 添加单元测试验证连接正确关闭

## 预估时间
1-2 小时

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "bug,priority-high,performance"

# Issue 3: API Key 启动验证缺失
echo "📝 创建 Issue 3/16: API Key 启动验证缺失"
gh issue create --title "🔴 API Key 启动验证缺失" --body "## 问题描述
应用启动时未验证 API Key 的有效性，导致运行时才发现配置错误。

## 影响
- 🔴 **稳定性问题**：服务启动后无法正常工作
- 调试困难，错误发现延迟
- 影响用户体验

## 文件位置
- \`llm/qwen_client.py\`

## 修复方案
1. 在应用启动时验证 API Key
2. 添加健康检查端点
3. 实现配置验证中间件
4. 提供清晰的错误提示信息

## 预估时间
30 分钟

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "bug,priority-high,startup"

# Issue 4: 数据库索引缺失
echo "📝 创建 Issue 4/16: 数据库索引缺失"
gh issue create --title "🔴 数据库索引缺失" --body "## 问题描述
关键查询字段缺少数据库索引，导致查询性能低下。

## 影响
- 🔴 **性能问题**：查询响应时间慢
- 数据库负载高
- 用户体验差

## 文件位置
- \`backend/models/\` 下多个模型文件

## 修复方案
1. 分析慢查询日志，识别需要索引的字段
2. 为常用查询字段添加索引（user_id, status, created_at 等）
3. 创建数据库迁移脚本
4. 添加性能测试验证索引效果

## 预估时间
2-3 小时

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "performance,database,priority-high"

# Issue 5: 并发控制竞态条件
echo "📝 创建 Issue 5/16: 并发控制竞态条件"
gh issue create --title "🔴 并发控制竞态条件" --body "## 问题描述
并发请求下存在竞态条件，可能导致数据不一致。

## 影响
- 🔴 **稳定性问题**：数据不一致
- 可能导致重复扣费或资源分配错误
- 难以复现和调试

## 文件位置
- \`backend/api/v1/generation.py\`

## 修复方案
1. 使用数据库事务和行级锁
2. 实现分布式锁（Redis Lock）
3. 添加乐观锁机制（version 字段）
4. 编写并发测试用例验证修复

## 预估时间
3-4 小时

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "bug,priority-high,concurrency"

# Issue 6: API 认证缺失
echo "📝 创建 Issue 6/16: API 认证缺失"
gh issue create --title "🔴 API 认证缺失" --body "## 问题描述
部分 API 端点缺少认证机制，存在未授权访问风险。

## 影响
- 🔴 **安全漏洞**：未授权用户可访问敏感接口
- 数据泄露风险
- 可能被恶意利用

## 文件位置
- \`backend/api/v1/\` 下多个端点

## 修复方案
1. 实现统一的认证中间件
2. 为所有 API 端点添加认证装饰器
3. 实现 JWT 或 Session 认证
4. 添加 API 访问日志和审计

## 预估时间
4-6 小时

## 优先级
🔴 高

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "security,priority-high,authentication"

# Issue 7: 类型注解不足
echo "📝 创建 Issue 7/16: 类型注解不足"
gh issue create --title "🟡 类型注解不足" --body "## 问题描述
代码中缺少类型注解，影响代码可读性和 IDE 支持。

## 影响
- 🟡 **可维护性**：代码理解困难
- IDE 自动补全和检查功能受限
- 增加重构难度

## 文件位置
- 多个 Python 文件

## 修复方案
1. 为函数参数和返回值添加类型注解
2. 使用 mypy 进行类型检查
3. 逐步补充现有代码的类型注解
4. 在 CI 中添加类型检查步骤

## 预估时间
4-6 小时

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "enhancement,code-quality,priority-medium"

# Issue 8: 内存泄漏风险
echo "📝 创建 Issue 8/16: 内存泄漏风险"
gh issue create --title "🟡 内存泄漏风险" --body "## 问题描述
部分代码存在潜在的内存泄漏风险，长期运行可能导致 OOM。

## 影响
- 🟡 **稳定性问题**：长期运行后内存占用持续增长
- 可能导致服务崩溃
- 需要定期重启

## 文件位置
- 多个模块

## 修复方案
1. 使用内存分析工具（memory_profiler）定位泄漏点
2. 检查全局变量和缓存机制
3. 实现对象池和资源回收机制
4. 添加内存监控和告警

## 预估时间
3-4 小时

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "bug,priority-medium,memory"

# Issue 9: CORS 配置过于宽松
echo "📝 创建 Issue 9/16: CORS 配置过于宽松"
gh issue create --title "🟡 CORS 配置过于宽松" --body "## 问题描述
CORS 配置允许所有来源访问，存在安全风险。

## 影响
- 🟡 **安全风险**：可能被恶意网站利用
- CSRF 攻击风险
- 数据泄露风险

## 文件位置
- \`backend/main.py\` 或 CORS 配置文件

## 修复方案
1. 限制允许的源为特定域名
2. 配置适当的 HTTP 方法白名单
3. 添加凭证（credentials）配置
4. 实现 CORS 预检缓存

## 预估时间
30 分钟

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "security,priority-medium,cors"

# Issue 10: 缺少输入验证
echo "📝 创建 Issue 10/16: 缺少输入验证"
gh issue create --title "🟡 缺少输入验证" --body "## 问题描述
部分 API 端点缺少输入验证，可能导致注入攻击或数据错误。

## 影响
- 🟡 **安全风险**：SQL 注入、XSS 等攻击风险
- 数据完整性问题
- 可能导致服务异常

## 文件位置
- \`backend/api/v1/\` 下多个端点

## 修复方案
1. 使用 Pydantic 模型进行输入验证
2. 添加字符串长度、格式、范围检查
3. 实现白名单验证机制
4. 添加输入验证单元测试

## 预估时间
2-3 小时

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "security,priority-medium,validation"

# Issue 11: 重试策略过于简单
echo "📝 创建 Issue 11/16: 重试策略过于简单"
gh issue create --title "🟡 重试策略过于简单" --body "## 问题描述
外部服务调用重试策略缺少指数退避和最大重试次数限制。

## 影响
- 🟡 **稳定性问题**：可能加剧外部服务压力
- 重试风暴风险
- 资源浪费

## 文件位置
- 多个外部服务调用模块

## 修复方案
1. 实现指数退避重试策略
2. 添加最大重试次数限制
3. 实现熔断器模式（Circuit Breaker）
4. 添加重试日志和监控

## 预估时间
2-3 小时

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "enhancement,priority-medium,reliability"

# Issue 12: 审查循环无熔断机制
echo "📝 创建 Issue 12/16: 审查循环无熔断机制"
gh issue create --title "🟡 审查循环无熔断机制" --body "## 问题描述
代码审查循环缺少熔断机制，可能导致无限循环或资源耗尽。

## 影响
- 🟡 **稳定性问题**：可能陷入无限循环
- 资源耗尽风险
- 服务不可用

## 文件位置
- 代码审查相关模块

## 修复方案
1. 添加最大迭代次数限制
2. 实现超时机制
3. 添加循环检测逻辑
4. 编写边界条件测试用例

## 预估时间
1-2 小时

## 优先级
🟡 中

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "bug,priority-medium,reliability"

# Issue 13: TODO 注释清理
echo "📝 创建 Issue 13/16: TODO 注释清理"
gh issue create --title "🟢 TODO 注释清理" --body "## 问题描述
代码中存在大量 TODO 注释，部分已过期或已完成。

## 影响
- 🟢 **可维护性**：代码整洁度下降
- 技术债务积累
- 影响代码可读性

## 文件位置
- 多个 Python 文件

## 修复方案
1. 扫描所有 TODO 注释
2. 分类处理：已完成、需保留、需创建 Issue
3. 更新或移除过期的 TODO
4. 建立 TODO 管理规范

## 预估时间
1-2 小时

## 优先级
🟢 低

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "enhancement,priority-low,cleanup"

# Issue 14: 配置验证不完整
echo "📝 创建 Issue 14/16: 配置验证不完整"
gh issue create --title "🟢 配置验证不完整" --body "## 问题描述
配置加载时缺少完整验证，可能导致运行时错误。

## 影响
- 🟢 **稳定性问题**：配置错误发现延迟
- 调试困难
- 影响开发体验

## 文件位置
- \`backend/config.py\`

## 修复方案
1. 实现配置 schema 验证
2. 添加配置项必填检查
3. 提供配置验证命令行工具
4. 在 CI 中添加配置检查步骤

## 预估时间
1-2 小时

## 优先级
🟢 低

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "enhancement,priority-low,configuration"

# Issue 15: 异常类不够细化
echo "📝 创建 Issue 15/16: 异常类不够细化"
gh issue create --title "🟢 异常类不够细化" --body "## 问题描述
异常处理使用通用 Exception，缺少细粒度的异常分类。

## 影响
- 🟢 **可维护性**：错误处理不精确
- 调试困难
- 用户体验差

## 文件位置
- 多个模块

## 修复方案
1. 定义自定义异常类层次结构
2. 区分业务异常、系统异常、验证异常
3. 实现统一的异常处理中间件
4. 添加异常日志和监控

## 预估时间
2-3 小时

## 优先级
🟢 低

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "enhancement,priority-low,error-handling"

# Issue 16: 文档字符串不一致
echo "📝 创建 Issue 16/16: 文档字符串不一致"
gh issue create --title "🟢 文档字符串不一致" --body "## 问题描述
函数和类的文档字符串格式不统一，部分缺失。

## 影响
- 🟢 **可维护性**：API 文档不完整
- 自动生成文档困难
- 新成员上手成本高

## 文件位置
- 多个 Python 文件

## 修复方案
1. 制定文档字符串规范（Google/NumPy 风格）
2. 补充缺失的文档字符串
3. 使用 Sphinx 或 mkdocs 生成文档
4. 在 CI 中添加文档检查

## 预估时间
3-4 小时

## 优先级
🟢 低

## 关联
- 关联代码审查报告：CODE_REVIEW_REPORT_20260320.md" --label "documentation,priority-low"

echo ""
echo "✅ 所有 16 个 GitHub Issues 创建完成！"
echo ""
echo "📋 Issue 列表:"
gh issue list --limit 16
