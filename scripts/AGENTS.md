# SCRIPTS 模块

**工具脚本**: 各种辅助脚本

## OVERVIEW

项目辅助脚本，包括测试运行、数据库管理、CI/CD等。

## KEY SCRIPTS

| 脚本 | 用途 |
|------|------|
| `ai_e2e_runner.py` | AI E2E测试运行器 |
| `auto_novel_process.py` | 自动小说生成流程 |
| `check_db_consistency.py` | 数据库一致性检查 |
| `cleanup_duplicate_characters.py` | 重复角色清理 |
| `generate_novel_tests.py` | 批量生成测试 |

## USAGE

```bash
# AI E2E测试
python scripts/ai_e2e_runner.py --mode autonomous --goal "测试目标"

# 数据库检查
python scripts/check_db_consistency.py --fix

# 清理重复角色
python scripts/cleanup_duplicate_characters.py --apply
```
