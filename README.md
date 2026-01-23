# HotSpot Hunter

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

HotSpot Hunter 是一个智能新闻热点追踪系统，提供新闻抓取、存储、AI分析和多平台推送功能。系统支持从多个新闻平台抓取热点新闻，使用 AI 进行重要性分析，并通过多种渠道推送重要新闻。

## ✨ 功能特性

- 📰 **多平台新闻抓取**: 支持从 NewsNow API 抓取多个平台的新闻数据
- 🗄️ **数据存储**: 基于 SQLite 的本地数据存储，支持按日期和平台分类
- 🤖 **AI 重要性分析**: 使用 AI 模型分析新闻重要性，支持批量分析
- 📊 **统计分析**: 提供新闻统计数据和平台分析
- 🔔 **多平台推送**: 支持飞书、钉钉、企业微信、Telegram、邮件、ntfy、Bark、Slack 等多种推送渠道
- 🔍 **智能筛选**: 支持关键词过滤和敏感词过滤
- ⏰ **定时任务**: 内置定时任务调度器，支持自动定时抓取
- 🚀 **RESTful API**: 基于 FastAPI 的高性能 API 服务
- 🐳 **Docker 支持**: 提供完整的 Docker 部署方案

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/starCarlos/HotSpot-Hunter.git
cd HotSpot-Hunter
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置应用**

复制配置文件并填入你的配置：
```bash
# AI 配置（用于新闻重要性分析）
cp config/ai_config.yaml.example config/ai_config.yaml
# 编辑 config/ai_config.yaml，填入你的 AI API Key

# 关键词配置（可选）
cp config/frequency_words.txt.example config/frequency_words.txt
# 编辑 config/frequency_words.txt，添加你的关键词规则

# 推送配置（可选）
cp config/notification_config.yaml.example config/notification_config.yaml
# 编辑 config/notification_config.yaml，配置推送渠道
```

4. **创建数据目录**
```bash
mkdir -p output
```

5. **运行服务**

```bash
# 开发模式
uvicorn main:app --reload --host 0.0.0.0 --port 1236

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 1236
```

6. **访问服务**

- API 文档: http://localhost:1236/docs
- 前端页面: http://localhost:1236/
- 健康检查: http://localhost:1236/api/health

### Docker 部署（推荐）

```bash
# 使用 Docker Compose
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

详细的 Docker 部署说明请参考 [DOCKER.md](DOCKER.md)

## 📖 使用指南

### 数据抓取

系统支持自动定时抓取和手动抓取两种方式：

**手动抓取**:
```bash
# Windows
crawl.bat

# Linux/Mac
chmod +x crawl.sh
./crawl.sh

# 或直接使用 Python
python crawl_data.py
```

**自动定时抓取**:
- 服务启动后，定时任务调度器会自动运行
- 默认每小时抓取一次
- 可通过环境变量 `CRAWL_INTERVAL_HOURS` 调整间隔
- 可通过环境变量 `CRAWL_SCHEDULER_ENABLED=false` 禁用定时任务

### API 使用

#### 查询新闻

```bash
# 查询今天的新闻
GET /api/news/?date=2026-01-23

# 查询特定平台的新闻
GET /api/news/?platform_id=v2ex

# 只获取最新一次抓取的数据
GET /api/news/?latest=true

# 限制返回数量
GET /api/news/?limit=10
```

#### 获取平台列表

```bash
GET /api/news/platforms
```

#### 获取统计数据

```bash
GET /api/news/stats?date=2026-01-23
```

#### 筛选新闻（基于关键词）

```bash
GET /api/filtered-news/?date=2026-01-23
```

更多 API 文档请访问 http://localhost:1236/docs

### 推送通知

系统支持多种推送渠道，配置方法请参考 [config/README.md](config/README.md)

支持的推送渠道：
- 飞书 (Feishu)
- 钉钉 (DingTalk)
- 企业微信 (WeCom)
- Telegram
- 邮件 (Email)
- ntfy
- Bark
- Slack
- 通用 Webhook

## 📁 项目结构

```
HotSpot-Hunter/
├── api/                    # API 路由模块
│   └── routes/            # 路由定义
│       ├── health.py      # 健康检查
│       ├── news.py        # 新闻查询
│       └── filtered_news.py  # 筛选新闻
├── app/                    # 应用核心模块
│   ├── ai/                # AI 分析模块
│   │   ├── analyzer.py    # AI 分析器
│   │   └── importance_analyzer.py  # 重要性分析
│   ├── crawler/           # 抓取模块
│   │   ├── fetcher.py     # 数据抓取
│   │   └── rss/           # RSS 抓取
│   ├── notification/      # 推送模块
│   │   ├── dispatcher.py  # 推送调度器
│   │   ├── senders.py     # 推送发送器
│   │   └── renderer.py    # 内容渲染
│   ├── storage/           # 存储模块
│   │   ├── manager.py     # 存储管理器
│   │   └── local.py       # 本地存储
│   ├── utils/             # 工具模块
│   ├── core/              # 核心功能
│   └── scheduler.py       # 定时任务调度器
├── config/                # 配置文件
│   ├── ai_config.yaml.example      # AI 配置示例
│   ├── frequency_words.txt.example # 关键词配置示例
│   ├── notification_config.yaml.example  # 推送配置示例
│   └── platform_types.yaml         # 平台类型配置
├── static/                # 静态文件（前端页面）
├── output/                # 数据输出目录
├── main.py                # FastAPI 应用入口
├── crawl_data.py          # 数据抓取脚本
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像定义
├── docker-compose.yml     # Docker Compose 配置
└── README.md              # 项目文档
```

## ⚙️ 配置说明

详细的配置说明请参考 [config/README.md](config/README.md)

主要配置文件：
- `config/ai_config.yaml` - AI 模型配置
- `config/frequency_words.txt` - 关键词和敏感词配置
- `config/platform_types.yaml` - 平台分类配置
- `config/notification_config.yaml` - 推送渠道配置

## 🔧 开发

### 本地开发

1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置环境变量或配置文件
4. 运行开发服务器：`uvicorn main:app --reload`

### 运行测试

项目使用 FastAPI 的内置测试功能，可以通过访问 API 文档页面进行测试：
- Swagger UI: http://localhost:1236/docs
- ReDoc: http://localhost:1236/redoc

### 代码规范

- 遵循 PEP 8 Python 代码规范
- 使用类型注解
- 添加必要的文档字符串

## 🤝 贡献

欢迎贡献代码！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何参与项目。

贡献方式：
- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交 Pull Request

## 📝 更新日志

### v1.0.0
- 初始版本发布
- 支持多平台新闻抓取
- 支持 AI 重要性分析
- 支持多平台推送
- 提供 RESTful API 服务

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的 Web 框架
- [NewsNow API](https://newsnow.io/) - 新闻数据源
- [TrendRadar](https://github.com/sansan0/TrendRadar) - 本项目从 TrendRadar 迁移了一部分模块（抓取、推送等）
- 所有贡献者和用户

## 📮 联系方式

- 项目地址: https://github.com/starCarlos/HotSpot-Hunter
- 问题反馈: https://github.com/starCarlos/HotSpot-Hunter/issues

---

⭐ 如果这个项目对你有帮助，请给个 Star！
