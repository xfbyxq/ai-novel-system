#!/bin/bash

# 数据库迁移脚本 - 使用 asyncpg 驱动
# 用法：./migrate_db.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "数据库迁移 - 使用 Python 脚本"
echo "============================================================"
echo ""

# 创建 Python 迁移脚本
cat > /tmp/migrate_db.py << 'PYEOF'
import asyncio
import asyncpg
import os
import sys

async def run_migration():
    # 从环境变量获取数据库配置
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_user = os.getenv('DB_USER', 'novel_user')
    db_password = os.getenv('DB_PASSWORD', 'novel_pass')
    db_name = os.getenv('DB_NAME', 'novel_system')
    
    # 构建连接 URL
    dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    print(f"连接到数据库：{dsn}")
    
    try:
        # 创建连接
        conn = await asyncpg.connect(dsn)
        print("✓ 数据库连接成功")
        
        # 检查表是否存在
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'chapters'
            );
        """)
        
        if not table_exists:
            print("⚠️  chapters 表不存在，先创建基础表结构...")
            # 这里可以添加创建基础表的 SQL
            # 为简单起见，我们只检查并添加字段
            print("请先运行主应用的数据库初始化")
            await conn.close()
            return False
        
        print("✓ chapters 表已存在")
        
        # 开始事务
        async with conn.transaction():
            # 添加 outline_task 字段
            await conn.execute("""
                ALTER TABLE chapters 
                ADD COLUMN IF NOT EXISTS outline_task JSONB DEFAULT '{}';
            """)
            print("✓ 已添加字段：outline_task (JSONB)")
            
            # 添加 outline_validation 字段
            await conn.execute("""
                ALTER TABLE chapters 
                ADD COLUMN IF NOT EXISTS outline_validation JSONB DEFAULT '{}';
            """)
            print("✓ 已添加字段：outline_validation (JSONB)")
            
            # 添加 outline_version 字段
            await conn.execute("""
                ALTER TABLE chapters 
                ADD COLUMN IF NOT EXISTS outline_version VARCHAR(50);
            """)
            print("✓ 已添加字段：outline_version (VARCHAR)")
            
            # 添加字段注释
            await conn.execute("""
                COMMENT ON COLUMN chapters.outline_task IS '本章的大纲任务配置（JSONB 格式）';
            """)
            await conn.execute("""
                COMMENT ON COLUMN chapters.outline_validation IS '大纲验证结果（JSONB 格式）';
            """)
            await conn.execute("""
                COMMENT ON COLUMN chapters.outline_version IS '使用的大纲版本号';
            """)
            print("✓ 已添加字段注释")
        
        # 验证迁移结果
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'chapters'
              AND column_name IN ('outline_task', 'outline_validation', 'outline_version')
            ORDER BY ordinal_position;
        """)
        
        print("\n迁移结果验证:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        await conn.close()
        print("\n✅ 数据库迁移成功完成！")
        return True
        
    except asyncpg.exceptions.UndefinedTableError as e:
        print(f"⚠️  错误：表不存在 - {e}")
        print("请先运行主应用的数据库初始化，或等待应用自动创建表结构")
        return False
    except Exception as e:
        print(f"❌ 迁移失败：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_migration())
    sys.exit(0 if success else 1)
PYEOF

# 在后端容器中执行迁移脚本
echo -e "${BLUE}在后端容器中执行迁移脚本...${NC}"
docker exec -e DB_HOST=postgres -e DB_PORT=5432 -e DB_USER=novel_user -e DB_PASSWORD=novel_pass -e DB_NAME=novel_system novel_backend python /tmp/migrate_db.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ 数据库迁移成功！${NC}"
    echo -e "${GREEN}============================================================${NC}"
else
    echo ""
    echo -e "${YELLOW}============================================================${NC}"
    echo -e "${YELLOW}⚠️  迁移未完成 - 表尚未创建${NC}"
    echo -e "${YELLOW}============================================================${NC}"
    echo ""
    echo -e "${BLUE}这是正常的，因为这是全新部署。${NC}"
    echo -e "${BLUE}应用启动后会自动创建基础表结构。${NC}"
    echo ""
    echo -e "${YELLOW}后续可以再次运行此脚本来添加新字段：${NC}"
    echo "  ./migrate_db.sh"
    echo ""
fi

# 清理临时文件
rm -f /tmp/migrate_db.py

echo ""
echo -e "${CYAN}验证服务状态：${NC}"
docker-compose ps

echo ""
echo -e "${CYAN}访问地址：${NC}"
echo "  前端：http://localhost:3000"
echo "  后端：http://localhost:8000"
echo "  API 文档：http://localhost:8000/docs"
echo ""
