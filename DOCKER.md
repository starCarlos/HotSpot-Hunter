# Docker 部署指南

本文档介绍如何使用 Docker 部署 HotSpot Hunter 项目。

## 📋 目录

- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [常用命令](#常用命令)
- [健康检查](#健康检查)
- [故障排查](#故障排查)
- [生产环境建议](#生产环境建议)

## 快速开始

### 使用 Docker Compose（推荐）

1. **准备配置文件**：
```bash
# 复制示例配置文件
cp config/ai_config.yaml.example config/ai_config.yaml
cp config/frequency_words.txt.example config/frequency_words.txt

# 编辑配置文件，填入你的配置
# config/ai_config.yaml - AI API Key
# config/frequency_words.txt - 关键词配置
```

2. **创建数据目录**：
```bash
mkdir -p output
```

3. **启动服务**：
```bash
# 生产模式
docker-compose up -d

# 开发模式（支持热重载）
docker-compose -f docker-compose.dev.yml up
```

4. **查看日志**：
```bash
docker-compose logs -f
```

5. **停止服务**：
```bash
docker-compose down
```

### 使用 Docker 命令

1. **构建镜像**：
```bash
docker build -t hotspot-hunter-api .
```

2. **运行容器**：
```bash
docker run -d \
  --name hotspot-hunter-api \
  -p 1236:1236 \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/output:/app/output \
  -e HOTSPOT_DATA_DIR=/app/output \
  hotspot-hunter-api
```

## 配置说明

### 环境变量

可以通过环境变量配置以下参数：

- `HOTSPOT_DATA_DIR`: 数据目录路径（默认：`/app/output`）
- `TZ`: 时区（默认：`Asia/Shanghai`）
- `CRAWL_SCHEDULER_ENABLED`: 是否启用定时任务（默认：`true`）
- `CRAWL_INTERVAL_HOURS`: 抓取间隔（小时）（默认：`1.0`）

### 数据持久化

Docker容器中的数据通过volume挂载到宿主机：

- `./config` → `/app/config` - 配置文件目录
- `./output` → `/app/output` - 数据目录（SQLite数据库、新闻数据）

### 推送配置（可选）

如果需要启用推送功能，需要配置推送渠道：

```bash
cp config/notification_config.yaml.example config/notification_config.yaml
# 编辑 config/notification_config.yaml，配置推送渠道
```

支持的推送渠道请参考 [config/README.md](config/README.md)

## 常用命令

### 查看容器状态
```bash
docker-compose ps
```

### 查看日志
```bash
# 实时日志
docker-compose logs -f

# 最近100行
docker-compose logs --tail=100
```

### 进入容器
```bash
docker-compose exec hotspot-hunter-api bash
```

### 重启服务
```bash
docker-compose restart
```

### 更新镜像
```bash
# 重新构建
docker-compose build

# 重启服务
docker-compose up -d
```

### 清理
```bash
# 停止并删除容器
docker-compose down

# 删除容器和镜像
docker-compose down --rmi all
```

## 健康检查

容器包含健康检查，可以通过以下方式查看：

```bash
docker-compose ps
```

健康检查端点：`http://localhost:1236/api/health`

## 故障排查

### 容器无法启动

1. 检查日志：
```bash
docker-compose logs hotspot-hunter-api
```

2. 检查端口是否被占用：
```bash
netstat -an | grep 1236
```

3. 检查配置文件是否存在：
```bash
ls -la config/
```

### 无法访问数据 / 页面没有数据

1. **检查数据目录是否存在**：
```bash
# 在宿主机上检查
ls -la output/

# 在容器内检查
docker-compose exec hotspot-hunter-api ls -la /app/output
```

2. **检查环境变量是否正确设置**：
```bash
docker-compose exec hotspot-hunter-api env | grep HOTSPOT_DATA_DIR
```

3. **检查数据目录挂载**：
```bash
# 检查volume挂载
docker-compose exec hotspot-hunter-api ls -la /app/output

# 检查是否有数据库文件
docker-compose exec hotspot-hunter-api find /app/output -name "*.db" -type f
```

4. **检查日志中的数据目录路径**：
查看容器日志，应该能看到类似 `[API] 使用数据目录: /app/output` 的日志。

5. **如果没有数据，需要先抓取数据**：
   
   应用启动时会自动启动定时任务调度器，默认每小时自动抓取一次数据。
   
   你也可以手动执行抓取：
   ```bash
   # 方式1：直接执行
   docker-compose exec hotspot-hunter-api python crawl_data.py
   
   # 方式2：进入容器后执行
   docker-compose exec hotspot-hunter-api bash
   python crawl_data.py
   ```
   
   抓取完成后，数据会保存到 `./output` 目录（已挂载到容器内的 `/app/output`）
   
   **定时任务配置**：
   - 默认启用定时任务，每小时抓取一次
   - 可通过环境变量 `CRAWL_SCHEDULER_ENABLED=false` 禁用定时任务
   - 可通过环境变量 `CRAWL_INTERVAL_HOURS=2.0` 设置抓取间隔（小时）
   - 查看定时任务状态：访问 `http://localhost:1236/api/health`

### AI分析不工作

1. 检查AI配置：
```bash
docker-compose exec hotspot-hunter-api cat /app/config/ai_config.yaml
```

2. 检查环境变量：
```bash
docker-compose exec hotspot-hunter-api env | grep AI_
```

## 生产环境建议

1. **使用环境变量文件**：
创建 `.env` 文件：
```bash
AI_API_KEY=your-api-key
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
```

在 `docker-compose.yml` 中引用：
```yaml
env_file:
  - .env
```

2. **限制资源使用**：
```yaml
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 512M
```

3. **使用反向代理**（如Nginx）：
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - hotspot-hunter-api
```

## 注意事项

1. **数据备份**：定期备份 `output/` 目录
2. **配置文件安全**：不要将包含敏感信息的配置文件提交到版本控制
3. **端口冲突**：确保端口1236未被占用
4. **时区设置**：容器内时区已设置为 `Asia/Shanghai`，可根据需要修改
5. **数据持久化**：确保数据目录已正确挂载，避免容器删除后数据丢失

## 相关文档

- [README.md](README.md) - 项目主文档
- [config/README.md](config/README.md) - 配置说明
- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南