#!/bin/bash

# 小说生成系统 - 完整重新部署脚本（包含数据库迁移）
# 用法：./redeploy_with_migration.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo "小说生成系统 - 完整重新部署（含数据库迁移）"
echo "============================================================"
echo ""

# 步骤 1: 停止旧容器
echo -e "${YELLOW}[1/6] 停止旧容器...${NC}"
docker-compose down
echo -e "${GREEN}✓ 容器已停止${NC}"
echo ""

# 步骤 2: 清理旧镜像（可选，加速构建）
echo -e "${YELLOW}[2/6] 清理旧镜像...${NC}"
docker rmi novel_system-backend novel_system-frontend 2>/dev/null || true
echo -e "${GREEN}✓ 旧镜像已清理${NC}"
echo ""

# 步骤 3: 重新构建镜像
echo -e "${YELLOW}[3/6] 构建新镜像...${NC}"
echo -e "${BLUE}正在构建后端镜像...${NC}"
docker-compose build backend
echo -e "${BLUE}正在构建前端镜像...${NC}"
docker-compose build frontend
echo -e "${GREEN}✓ 镜像构建完成${NC}"
echo ""

# 步骤 4: 启动基础服务（PostgreSQL 和 Redis）
echo -e "${YELLOW}[4/6] 启动基础服务...${NC}"
docker-compose up -d postgres redis
echo -e "${BLUE}等待数据库启动...${NC}"
sleep 5

# 检查数据库是否就绪
for i in {1..10}; do
    if docker exec novel_postgres pg_isready -U novel_user -d novel_system > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 数据库已就绪${NC}"
        break
    fi
    echo -e "${YELLOW}等待数据库启动... ($i/10)${NC}"
    sleep 2
done
echo ""

# 步骤 5: 执行数据库迁移
echo -e "${YELLOW}[5/6] 执行数据库迁移...${NC}"

# 方法 1: 使用 Alembic 自动迁移（推荐）
echo -e "${BLUE}运行 Alembic 迁移...${NC}"

# 创建临时迁移容器
docker run --rm \
    --network novel_system_default \
    --env DB_HOST=postgres \
    --env DB_PORT=5432 \
    --env DB_USER=novel_user \
    --env DB_PASSWORD=novel_pass \
    --env DB_NAME=novel_system \
    novel_system-backend \
    alembic upgrade head

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 数据库迁移成功${NC}"
else
    echo -e "${RED}✗ 数据库迁移失败${NC}"
    echo -e "${YELLOW}尝试手动执行迁移脚本...${NC}"
    
    # 方法 2: 手动执行迁移脚本
    docker exec -i novel_postgres psql -U novel_user -d novel_system << 'EOSQL'
-- 检查并添加 outline_task 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_task'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_task JSONB DEFAULT '{}';
        RAISE NOTICE 'Added column outline_task to chapters table';
    ELSE
        RAISE NOTICE 'Column outline_task already exists';
    END IF;
END $$;

-- 检查并添加 outline_validation 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_validation'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_validation JSONB DEFAULT '{}';
        RAISE NOTICE 'Added column outline_validation to chapters table';
    ELSE
        RAISE NOTICE 'Column outline_validation already exists';
    END IF;
END $$;

-- 检查并添加 outline_version 字段
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chapters' AND column_name = 'outline_version'
    ) THEN
        ALTER TABLE chapters ADD COLUMN outline_version VARCHAR(50);
        RAISE NOTICE 'Added column outline_version to chapters table';
    ELSE
        RAISE NOTICE 'Column outline_version already exists';
    END IF;
END $$;
EOSQL
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 手动迁移成功${NC}"
    else
        echo -e "${RED}✗ 手动迁移失败，请检查数据库日志${NC}"
        exit 1
    fi
fi

# 验证迁移结果
echo ""
echo -e "${BLUE}验证迁移结果...${NC}"
docker exec -i novel_postgres psql -U novel_user -d novel_system -c "\d chapters" | grep -E "outline_task|outline_validation|outline_version" || {
    echo -e "${RED}✗ 验证失败：新字段未找到${NC}"
    exit 1
}
echo -e "${GREEN}✓ 迁移验证成功${NC}"
echo ""

# 步骤 6: 启动所有服务
echo -e "${YELLOW}[6/6] 启动所有服务...${NC}"
docker-compose up -d backend frontend
echo -e "${BLUE}等待服务启动...${NC}"
sleep 10

# 检查服务状态
echo ""
echo -e "${GREEN}服务状态：${NC}"
docker-compose ps

echo ""
echo "============================================================"
echo -e "${GREEN}部署完成！${NC}"
echo "============================================================"
echo ""
echo "访问地址："
echo -e "  ${BLUE}前端：${NC}http://localhost:3000"
echo -e "  ${BLUE}后端 API: ${NC}http://localhost:8000"
echo -e "  ${BLUE}API 文档：${NC}http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}数据库迁移信息：${NC}"
echo "  - 新增字段：outline_task, outline_validation, outline_version"
echo "  - 数据表：chapters"
echo ""
echo -e "${YELLOW}查看日志：${NC}"
echo "  docker-compose logs -f backend"
echo "  docker-compose logs -f frontend"
echo ""
