# ========== 构建阶段 ==========
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install --no-cache-dir poetry==1.8.2

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 配置 Poetry - 安装到 /app 目录
RUN poetry config virtualenvs.create false \
    && poetry config installer.modern-installation false

# 安装依赖
RUN poetry install --no-interaction --no-ansi --only main

# ========== 运行阶段 ==========
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 设置 Python 路径
ENV PYTHONPATH=/app/lib/python3.12/site-packages:$PYTHONPATH

# 从构建阶段复制 Python 包
COPY --from=builder /usr/local/lib/python3.12/site-packages /app/lib/python3.12/site-packages

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
