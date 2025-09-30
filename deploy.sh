#!/bin/bash
set -e

# 检查环境变量
if [ -z "$OPENAI_API_KEY" ] || [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "请设置OPENAI_API_KEY和ANTHROPIC_API_KEY环境变量"
  exit 1
fi

# 构建并启动服务
echo "开始部署..."
docker-compose down
docker-compose up -d --build

# 初始化数据库
echo "初始化数据库..."
docker-compose exec -T postgres psql -U spatial_user -d spatiotemporal_rag <<EOF
CREATE EXTENSION IF NOT EXISTS postgis;
EOF

echo "部署完成！访问 http://localhost 即可使用"