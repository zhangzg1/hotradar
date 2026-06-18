# AI Hotspot Monitor - All-in-One Docker Image
# 包含前端(nginx)、后端(fastapi)的完整应用

# ==================== Stage 1: 前端构建 ====================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制前端依赖文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci

# 复制前端源代码
COPY frontend/ ./

# 构建前端
RUN npm run build

# ==================== Stage 2: 最终镜像 ====================
FROM python:3.10-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# 安装系统依赖：nginx + supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 Python 依赖文件
COPY backend/requirements.txt ./backend/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制后端代码
COPY backend/ ./backend/
COPY llm/ ./llm/
COPY agents/ ./agents/
COPY scripts/ ./scripts/

# 从前端构建阶段复制构建产物到 nginx 目录
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# 复制 nginx 配置
COPY docker/nginx.conf /etc/nginx/nginx.conf

# 复制 supervisor 配置
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建日志目录
RUN mkdir -p /app/logs /var/log/supervisor

# 创建非 root 用户（可选，nginx 和 supervisor 需要 root 启动）
# RUN useradd --create-home --shell /bin/bash appuser

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# 使用 supervisor 启动所有服务
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
