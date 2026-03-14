#!/bin/bash

# 直接在 PostgreSQL 容器中创建所有表
# 用法：./create_tables.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================================"
echo "在 PostgreSQL 容器中创建所有表"
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

echo -e "${BLUE}连接到数据库容器...${NC}"
echo ""

# 执行 SQL 创建所有表
docker exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME << 'EOSQL'
-- ============================================================
-- 小说生成系统 - 数据库表结构创建脚本
-- ============================================================

BEGIN;

-- 创建枚举类型（必须在表之前创建）
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskstatus') THEN
        CREATE TYPE taskstatus AS ENUM ('pending', 'running', 'success', 'failed', 'cancelled');
        RAISE NOTICE '✓ 已创建枚举类型：taskstatus';
    END IF;
END $$;

-- 1. 小说表
CREATE TABLE IF NOT EXISTS novels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    genre VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    author VARCHAR(100),
    word_count INTEGER DEFAULT 0,
    chapter_count INTEGER DEFAULT 0,
    tags JSONB DEFAULT '[]',
    platform VARCHAR(100),
    platform_id VARCHAR(200),
    length_type VARCHAR(50) DEFAULT 'medium',
    token_cost DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. 世界观设定表
CREATE TABLE IF NOT EXISTS world_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    world_name VARCHAR(200),
    world_type VARCHAR(100),
    power_system JSONB,
    geography JSONB,
    factions JSONB,
    rules JSONB,
    timeline JSONB,
    special_elements JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. 角色表
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50),
    gender VARCHAR(20),
    age VARCHAR(50),
    appearance TEXT,
    personality TEXT,
    background TEXT,
    abilities JSONB,
    relationships JSONB,
    character_arc TEXT,
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. 角色名称版本表
CREATE TABLE IF NOT EXISTS character_name_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. 情节大纲表
CREATE TABLE IF NOT EXISTS plot_outlines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    structure_type VARCHAR(50),
    volumes JSONB,
    main_plot JSONB,
    main_plot_detailed JSONB,
    sub_plots JSONB,
    key_turning_points JSONB,
    climax_chapter INTEGER,
    raw_content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. 章节表
CREATE TABLE IF NOT EXISTS chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    volume_number INTEGER DEFAULT 1,
    title VARCHAR(200),
    content TEXT,
    word_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'draft',
    outline JSONB,
    characters_appeared UUID[],
    plot_points JSONB,
    foreshadowing JSONB,
    quality_score FLOAT,
    continuity_issues JSONB,
    detailed_outline JSONB,
    outline_task JSONB DEFAULT '{}',
    outline_validation JSONB DEFAULT '{}',
    outline_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE
);

-- 7. 生成任务表
CREATE TABLE IF NOT EXISTS generation_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_id UUID REFERENCES chapters(id) ON DELETE SET NULL,
    task_type VARCHAR(50),
    status taskstatus DEFAULT 'pending',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 8. Token 使用表
CREATE TABLE IF NOT EXISTS token_usages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id UUID REFERENCES novels(id) ON DELETE SET NULL,
    task_id UUID REFERENCES generation_tasks(id) ON DELETE SET NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost DECIMAL(10, 6) DEFAULT 0,
    model VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. 平台账户表
CREATE TABLE IF NOT EXISTS platform_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(100) NOT NULL,
    account_name VARCHAR(200),
    account_id VARCHAR(200),
    credentials JSONB,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. 发布任务表
CREATE TABLE IF NOT EXISTS publish_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    platform_account_id UUID REFERENCES platform_accounts(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending',
    scheduled_at TIMESTAMP WITH TIME ZONE,
    published_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. 章节发布表
CREATE TABLE IF NOT EXISTS chapter_publishes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    platform VARCHAR(100),
    platform_chapter_id VARCHAR(200),
    status VARCHAR(50),
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 12. 小说创建流程表
CREATE TABLE IF NOT EXISTS novel_creation_flows (
    id VARCHAR(100) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    novel_id VARCHAR(100),
    scene VARCHAR(50) DEFAULT 'create',
    current_step VARCHAR(50) DEFAULT 'initial',
    genre VARCHAR(100),
    world_setting_data JSONB,
    synopsis_data JSONB,
    novel_title VARCHAR(200),
    tags JSONB,
    target_platform VARCHAR(100) DEFAULT '番茄小说',
    length_type VARCHAR(50) DEFAULT 'medium',
    selected_novel_id VARCHAR(100),
    query_target VARCHAR(100),
    query_result JSONB,
    revision_target VARCHAR(100),
    revision_details JSONB,
    genre_confirmed BOOLEAN DEFAULT FALSE,
    world_setting_confirmed BOOLEAN DEFAULT FALSE,
    synopsis_confirmed BOOLEAN DEFAULT FALSE,
    final_confirmed BOOLEAN DEFAULT FALSE,
    revision_confirmed BOOLEAN DEFAULT FALSE,
    conversation_history JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. Agent 活动表
CREATE TABLE IF NOT EXISTS agent_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(100),
    action VARCHAR(100),
    novel_id UUID,
    chapter_id UUID,
    input_data JSONB,
    output_data JSONB,
    status VARCHAR(50),
    error_message TEXT,
    duration_ms INTEGER,
    token_cost DECIMAL(10, 6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. AI 聊天会话表
CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    novel_id UUID REFERENCES novels(id) ON DELETE SET NULL,
    novel_title VARCHAR(200),
    messages JSONB,
    context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_chapters_novel_id ON chapters(novel_id);
CREATE INDEX IF NOT EXISTS idx_chapters_status ON chapters(status);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_novel_id ON generation_tasks(novel_id);
CREATE INDEX IF NOT EXISTS idx_generation_tasks_status ON generation_tasks(status);
CREATE INDEX IF NOT EXISTS idx_characters_novel_id ON characters(novel_id);
CREATE INDEX IF NOT EXISTS idx_world_settings_novel_id ON world_settings(novel_id);
CREATE INDEX IF NOT EXISTS idx_plot_outlines_novel_id ON plot_outlines(novel_id);
CREATE INDEX IF NOT EXISTS idx_novel_creation_flows_session_id ON novel_creation_flows(session_id);
CREATE INDEX IF NOT EXISTS idx_novel_creation_flows_novel_id ON novel_creation_flows(novel_id);
CREATE INDEX IF NOT EXISTS idx_agent_activities_novel_id ON agent_activities(novel_id);
CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_novel_id ON ai_chat_sessions(novel_id);

COMMIT;

-- 显示所有表
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
EOSQL

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ 所有表创建成功！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    
    # 显示表数量
    TABLE_COUNT=$(docker exec novel_postgres psql -U novel_user -d novel_system -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    echo -e "${BLUE}数据库表现状：${NC}$TABLE_COUNT 个表"
    echo ""
else
    echo -e "${RED}✗ 表创建失败${NC}"
    exit 1
fi
