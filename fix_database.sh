#!/bin/bash

# 修复数据库表缺失问题
# 用法：./fix_database.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "修复数据库表缺失问题"
echo "============================================================"
echo ""

# 检查数据库容器
if ! docker ps | grep -q novel_postgres; then
    echo -e "${RED}错误：数据库容器未运行${NC}"
    exit 1
fi

echo -e "${BLUE}检查数据库状态...${NC}"
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

if [ "$TABLE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}数据库为空，需要执行完整迁移...${NC}"
else
    echo -e "${GREEN}数据库已有 $TABLE_COUNT 个表${NC}"
fi

echo ""
echo -e "${BLUE}停止后端服务...${NC}"
docker-compose stop backend

echo ""
echo -e "${YELLOW}[步骤 1/3] 使用 Alembic 执行迁移...${NC}"

# 方法 1: 使用 Alembic
if docker run --rm \
    --network novel_system_default \
    -e DB_HOST=postgres \
    -e DB_PORT=5432 \
    -e DB_USER=novel_user \
    -e DB_PASSWORD=novel_pass \
    -e DB_NAME=novel_system \
    novel_system-backend \
    alembic upgrade head 2>&1; then
    echo -e "${GREEN}✓ Alembic 迁移成功${NC}"
else
    echo -e "${YELLOW}Alembic 迁移失败，使用备用方案...${NC}"
    echo ""
    
    # 方法 2: 直接创建所有表
    echo -e "${BLUE}[步骤 2/3] 使用 SQLAlchemy 创建所有表...${NC}"
    
    docker run --rm \
        --network novel_system_default \
        -e DB_HOST=postgres \
        -e DB_PORT=5432 \
        -e DB_USER=novel_user \
        -e DB_PASSWORD=novel_pass \
        -e DB_NAME=novel_system \
        novel_system-backend \
        python << 'PYEOF'
import asyncio
import asyncpg
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.models import (  # noqa: F401
    Novel, WorldSetting, Character, PlotOutline,
    Chapter, GenerationTask, TokenUsage,
    PlatformAccount, PublishTask, ChapterPublish,
    NovelCreationFlow, AgentActivity, AIChatSession,
    CharacterNameVersion,
)

# 创建数据库引擎
db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(db_url)

print("创建所有数据库表...")
Base.metadata.create_all(bind=engine)
print("✓ 所有表已创建")

# 验证
async def verify():
    conn = await asyncpg.connect(db_url)
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    print(f"✓ 已创建 {len(tables)} 个表:")
    for table in tables:
        print(f"  - {table['table_name']}")
    await conn.close()

asyncio.run(verify())
PYEOF
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 表创建成功${NC}"
    else
        echo -e "${RED}✗ 表创建失败${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}[步骤 3/3] 验证数据库表...${NC}"
TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo -e "${GREEN}数据库现在有 $TABLE_COUNT 个表${NC}"

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ 数据库修复成功！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "${BLUE}重启后端服务...${NC}"
    docker-compose start backend
    
    sleep 5
    
    echo ""
    echo -e "${CYAN}服务状态：${NC}"
    docker-compose ps
    
    echo ""
    echo -e "${CYAN}访问地址：${NC}"
    echo "  前端：http://localhost:3000"
    echo "  后端：http://localhost:8000"
    echo "  API 文档：http://localhost:8000/docs"
    echo ""
else
    echo -e "${RED}✗ 数据库仍然为空，请检查日志${NC}"
    exit 1
fi
