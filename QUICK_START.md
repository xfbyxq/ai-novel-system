# 🚀 快速部署指南

## 一键部署（推荐）

```bash
# 执行完整部署（包含数据库迁移）
./deploy_complete.sh
```

## 部署后访问地址

- **前端**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

---

## 可用脚本

### 1. `deploy_complete.sh` - 完整部署

```bash
# 标准部署
./deploy_complete.sh

# 全新部署（清理所有数据）
./deploy_complete.sh --clean

# 仅数据库迁移
./deploy_complete.sh --migrate

# 仅重启服务
./deploy_complete.sh --restart
```

### 2. `run_migration.sh` - 数据库迁移

```bash
# 在运行的数据库中执行迁移
./run_migration.sh
```

### 3. `migrate_db.sh` - Python 迁移脚本

```bash
# 使用 asyncpg 执行迁移
./migrate_db.sh
```

---

## 验证部署

```bash
# 检查服务状态
docker-compose ps

# 查看后端日志
docker-compose logs backend

# 查看前端日志
docker-compose logs frontend
```

---

## 新增功能

本次部署包含**大纲系统**完整功能：

1. ✅ 完整大纲梳理（含结局设计）
2. ✅ 章节拆分与主线细化
3. ✅ 章节创作前大纲校验
4. ✅ 大纲版本管理

---

## 数据库变更

为 `chapters` 表添加了三个新字段：

- `outline_task` (JSONB) - 本章大纲任务
- `outline_validation` (JSONB) - 大纲验证结果  
- `outline_version` (VARCHAR) - 大纲版本号

---

## 故障排查

**问题**: 数据库迁移失败

**解决**: 
```bash
# 重启后端服务
docker-compose restart backend

# 再次执行迁移
./run_migration.sh
```

**问题**: 无法访问服务

**解决**:
```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重新部署
./deploy_complete.sh --clean
```

---

详细文档请查看：
- `DEPLOYMENT_GUIDE.md` - 完整部署指南
- `DEPLOYMENT_SUMMARY.md` - 部署总结报告
