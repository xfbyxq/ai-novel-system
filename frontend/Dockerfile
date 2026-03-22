# ========== 构建阶段 ==========
FROM node:20-alpine AS builder

WORKDIR /app

# 设置 npm 镜像
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 复制 package 文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci --registry=${NPM_REGISTRY}

# 复制前端源代码
COPY frontend/ ./

# 构建生产版本
RUN npm run build

# ========== 运行阶段 ==========
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
