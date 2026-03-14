#!/bin/bash

# 数据库迁移脚本 - 直接在运行的容器中执行
# 用法：./run_migration.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "小说生成系统 - 数据库迁移脚本"
echo "============================================================"
echo ""

CONTAINER_NAME="novel_postgres"
DB_USER="novel_user"
DB_NAME="novel_system"

# 检查容器是否运行
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}错误：数据库容器未运行${NC}"
    echo -e "${YELLOW}请先启动容器：docker-compose up -d postgres${NC}"
    exit 1
fi

echo -e "${BLUE}连接到数据库容器：${NC}$CONTAINER_NAME"
echo ""

# 方法 1: 使用 Alembic 迁移
echo -e "${YELLOW}[方法 1] 尝试使用 Alembic 自动迁移...${NC}"

# 检查后端容器是否存在
if docker ps | grep -q novel_backend; then
    echo -e "${BLUE}在后端容器中执行 Alembic 迁移...${NC}"
    docker exec novel_backend alembic upgrade head
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Alembic 迁移成功${NC}"
        echo ""
    else
        echo -e "${RED}✗ Alembic 迁移失败${NC}"
        echo -e "${YELLOW}回退到方法 2：手动执行 SQL 迁移${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}后端容器未运行，使用手动 SQL 迁移${NC}"
    echo ""
fi

# 方法 2: 手动 SQL 迁移
echo -e "${YELLOW}[方法 2] 执行手动 SQL 迁移...${NC}"

docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME << 'EOSQL'
-- ============================================================
-- 小说大纲系统 - 数据库迁移脚本
-- 版本：1.0
-- 日期：2026-03-13
-- 说明：为 chapters 表添加大纲相关字段
-- ============================================================

BEGIN;

-- 1. 添加 outline_task 字段（JSONB 类型）
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'chapters' 
        AND column_name = 'outline_task'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_task JSONB DEFAULT '{}';
        RAISE NOTICE '✓ 已添加字段：outline_task (JSONB)';
    ELSE
        RAISE NOTICE 'ℹ 字段已存在：outline_task';
    END IF;
END $$;

-- 2. 添加 outline_validation 字段（JSONB 类型）
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'chapters' 
        AND column_name = 'outline_validation'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_validation JSONB DEFAULT '{}';
        RAISE NOTICE '✓ 已添加字段：outline_validation (JSONB)';
    ELSE
        RAISE NOTICE 'ℹ 字段已存在：outline_validation';
    END IF;
END $$;

-- 3. 添加 outline_version 字段（VARCHAR 类型）
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'chapters' 
        AND column_name = 'outline_version'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_version VARCHAR(50);
        RAISE NOTICE '✓ 已添加字段：outline_version (VARCHAR(50))';
    ELSE
        RAISE NOTICE 'ℹ 字段已存在：outline_version';
    END IF;
END $$;

-- 4. 为新增字段添加注释
COMMENT ON COLUMN chapters.outline_task IS '本章的大纲任务配置（JSONB 格式）';
COMMENT ON COLUMN chapters.outline_validation IS '大纲验证结果（JSONB 格式）';
COMMENT ON COLUMN chapters.outline_version IS '使用的大纲版本号';

COMMIT;

-- 5. 显示 chapters 表结构
\d chapters

-- 6. 验证新增字段
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'chapters'
  AND column_name IN ('outline_task', 'outline_validation', 'outline_version')
ORDER BY ordinal_position;

EOSQL

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ 数据库迁移成功完成！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    
    # 显示迁移统计
    echo -e "${BLUE}迁移统计：${NC}"
    docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -t -c \
        "SELECT COUNT(*) || ' 条记录已更新' FROM chapters;"
    
    echo ""
    echo -e "${YELLOW}新增字段说明：${NC}"
    echo "  1. outline_task (JSONB)      - 本章的大纲任务配置"
    echo "  2. outline_validation (JSONB) - 大纲验证结果"
    echo "  3. outline_version (VARCHAR)  - 使用的大纲版本号"
    echo ""
else
    echo ""
    echo -e "${RED}============================================================${NC}"
    echo -e "${RED}✗ 数据库迁移失败${NC}"
    echo -e "${RED}============================================================${NC}"
    echo ""
    echo -e "${YELLOW}请检查：${NC}"
    echo "  1. 数据库容器是否正常运行"
    echo "  2. 数据库连接配置是否正确"
    echo "  3. 查看数据库日志：docker logs $CONTAINER_NAME"
    echo ""
    exit 1
fi
