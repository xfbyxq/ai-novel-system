#!/bin/bash

# 修复数据库缺失的枚举类型和字段
# 用法：./fix_database_types.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "修复数据库缺失的枚举类型和字段"
echo "============================================================"
echo ""

CONTAINER_NAME="novel_postgres"
DB_USER="novel_user"
DB_NAME="novel_system"

# 检查容器
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo -e "${RED}错误：数据库容器未运行${NC}"
    exit 1
fi

echo -e "${BLUE}连接到数据库...${NC}"
echo ""

# 执行 SQL 修复
docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME << 'EOSQL'
BEGIN;

-- 1. 创建 TaskStatus 枚举类型
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
        CREATE TYPE taskstatus AS ENUM (
            'pending',
            'running',
            'success',
            'failed',
            'cancelled'
        );
        RAISE NOTICE '✓ 已创建枚举类型：taskstatus';
    ELSE
        RAISE NOTICE 'ℹ 枚举类型已存在：taskstatus';
    END IF;
END $$;

-- 2. 为 novels 表添加 cover_url 字段
ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS cover_url VARCHAR(500);

-- 添加字段注释
COMMENT ON COLUMN novels.cover_url IS '封面图片 URL';

-- 3. 为 generation_tasks 表的 status 字段设置默认类型
-- 如果 status 字段不存在则创建
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'generation_tasks' AND column_name = 'status'
    ) THEN
        ALTER TABLE generation_tasks 
        ADD COLUMN status taskstatus DEFAULT 'pending';
        RAISE NOTICE '✓ 已添加字段：generation_tasks.status';
    ELSE
        RAISE NOTICE 'ℹ 字段已存在：generation_tasks.status';
    END IF;
END $$;

-- 4. 添加其他可能缺失的字段到 novels 表
ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS synopsis TEXT;

ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS target_platform VARCHAR(100);

ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS estimated_revenue DECIMAL(10, 2);

ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS actual_revenue DECIMAL(10, 2);

ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS chapter_config JSONB DEFAULT '{}';

ALTER TABLE novels 
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- 添加注释
COMMENT ON COLUMN novels.synopsis IS '小说简介';
COMMENT ON COLUMN novels.target_platform IS '目标发布平台';
COMMENT ON COLUMN novels.estimated_revenue IS '预估收入';
COMMENT ON COLUMN novels.actual_revenue IS '实际收入';
COMMENT ON COLUMN novels.chapter_config IS '章节配置';
COMMENT ON COLUMN novels.metadata IS '元数据';

COMMIT;

-- 验证修复结果
SELECT '枚举类型:' as info;
SELECT typname FROM pg_type WHERE typname = 'taskstatus';

SELECT 'novels 表结构:' as info;
\d novels

SELECT 'generation_tasks 表结构:' as info;
\d generation_tasks

EOSQL

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ 数据库修复成功！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "${BLUE}已修复内容：${NC}"
    echo "  1. ✓ 创建枚举类型 taskstatus"
    echo "  2. ✓ 添加 novels.cover_url 字段"
    echo "  3. ✓ 添加 novels.synopsis 字段"
    echo "  4. ✓ 添加 novels.target_platform 字段"
    echo "  5. ✓ 添加 novels.estimated_revenue 字段"
    echo "  6. ✓ 添加 novels.actual_revenue 字段"
    echo "  7. ✓ 添加 novels.chapter_config 字段"
    echo "  8. ✓ 添加 novels.metadata 字段"
    echo ""
else
    echo -e "${RED}✗ 数据库修复失败${NC}"
    exit 1
fi
