"""
数据库迁移脚本：创建 agent_activities 表

此脚本创建 agent_activities 表用于记录每个 Agent 的详细活动

使用方法：
    python -m migrations.create_agent_activities_table
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import engine


async def migrate():
    """执行数据库迁移"""
    print("开始创建 agent_activities 表...")
    
    async with engine.begin() as conn:
        # 创建 agent_activities 表
        print("1. 创建 agent_activities 表...")
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_activities (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
                    task_id UUID NOT NULL REFERENCES generation_tasks(id) ON DELETE CASCADE,
                    agent_name VARCHAR(100) NOT NULL,
                    agent_role VARCHAR(200),
                    activity_type VARCHAR(50) NOT NULL,
                    phase VARCHAR(50),
                    step_number INTEGER,
                    iteration_number INTEGER,
                    input_data JSONB DEFAULT '{}',
                    output_data JSONB DEFAULT '{}',
                    raw_output TEXT,
                    metadata JSONB DEFAULT '{}',
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    cost NUMERIC(10, 6) DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'success',
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            print("   ✅ agent_activities 表创建成功")
        except Exception as e:
            print(f"   ⚠️  agent_activities 表可能已存在：{e}")
        
        # 创建索引
        print("2. 创建索引...")
        try:
            # novel_id 索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_novel_id 
                ON agent_activities(novel_id)
            """))
            print("   ✅ idx_agent_activities_novel_id 索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_novel_id 索引可能已存在：{e}")
        
        try:
            # task_id 索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_task_id 
                ON agent_activities(task_id)
            """))
            print("   ✅ idx_agent_activities_task_id 索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_task_id 索引可能已存在：{e}")
        
        try:
            # agent_name 索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_agent_name 
                ON agent_activities(agent_name)
            """))
            print("   ✅ idx_agent_activities_agent_name 索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_agent_name 索引可能已存在：{e}")
        
        try:
            # activity_type 索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_activity_type 
                ON agent_activities(activity_type)
            """))
            print("   ✅ idx_agent_activities_activity_type 索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_activity_type 索引可能已存在：{e}")
        
        try:
            # 复合索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_novel_task 
                ON agent_activities(novel_id, task_id)
            """))
            print("   ✅ idx_agent_activities_novel_task 复合索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_novel_task 复合索引可能已存在：{e}")
        
        try:
            # created_at 索引
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_agent_activities_created 
                ON agent_activities(created_at)
            """))
            print("   ✅ idx_agent_activities_created 索引创建成功")
        except Exception as e:
            print(f"   ⚠️  idx_agent_activities_created 索引可能已存在：{e}")
        
        # 更新 generation_tasks 表的 agent_logs 字段注释
        print("3. 更新 generation_tasks 表注释...")
        try:
            await conn.execute(text("""
                COMMENT ON COLUMN generation_tasks.agent_logs IS 
                'Agent 日志摘要（详细日志请查看 agent_activities 表）'
            """))
            print("   ✅ generation_tasks.agent_logs 注释更新成功")
        except Exception as e:
            print(f"   ⚠️  注释更新失败：{e}")
    
    print("\n✅ 数据库迁移完成！")
    print("\n新增表说明：")
    print("- agent_activities: 记录每个 Agent 的详细活动，包括输入输出、Token 使用、成本等")
    print("\n索引说明：")
    print("- idx_agent_activities_novel_id: 按小说 ID 查询")
    print("- idx_agent_activities_task_id: 按任务 ID 查询")
    print("- idx_agent_activities_agent_name: 按 Agent 名称查询")
    print("- idx_agent_activities_activity_type: 按活动类型查询")
    print("- idx_agent_activities_novel_task: 复合查询优化")
    print("- idx_agent_activities_created: 按时间排序查询")


async def rollback():
    """回滚迁移（仅用于测试）"""
    print("开始回滚数据库迁移...")
    
    async with engine.begin() as conn:
        # 删除 agent_activities 表
        print("1. 删除 agent_activities 表...")
        try:
            await conn.execute(text("""
                DROP TABLE IF EXISTS agent_activities CASCADE
            """))
            print("   ✅ agent_activities 表已删除")
        except Exception as e:
            print(f"   ⚠️  删除失败：{e}")
    
    print("\n⚠️  数据库迁移已回滚！")


async def check_migration_status():
    """检查迁移状态"""
    print("检查数据库迁移状态...")
    
    async with engine.begin() as conn:
        # 检查 agent_activities 表
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name = 'agent_activities'
        """))
        row = result.fetchone()
        if row:
            print("✅ agent_activities 表存在")
            
            # 检查记录数
            count_result = await conn.execute(text("""
                SELECT COUNT(*) FROM agent_activities
            """))
            count = count_result.scalar()
            print(f"   当前记录数：{count}")
        else:
            print("❌ agent_activities 表不存在")
        
        # 检查索引
        result = await conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'agent_activities'
        """))
        indexes = [row[0] for row in result.fetchall()]
        if indexes:
            print(f"✅ 索引数量：{len(indexes)}")
            for idx in indexes:
                print(f"   - {idx}")
        else:
            print("❌ 未找到索引")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库迁移脚本：创建 agent_activities 表")
    parser.add_argument(
        "--action",
        choices=["migrate", "rollback", "check"],
        default="migrate",
        help="执行的操作：migrate(迁移), rollback(回滚), check(检查状态)"
    )
    
    args = parser.parse_args()
    
    if args.action == "migrate":
        await migrate()
    elif args.action == "rollback":
        confirmation = input("⚠️  确定要回滚迁移吗？此操作不可逆！(yes/no): ")
        if confirmation.lower() == "yes":
            await rollback()
        else:
            print("回滚已取消")
    elif args.action == "check":
        await check_migration_status()


if __name__ == "__main__":
    asyncio.run(main())
