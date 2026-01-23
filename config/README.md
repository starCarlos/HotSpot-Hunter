# 配置文件说明

本文档介绍 HotSpot Hunter 项目的所有配置文件及其使用方法。

## 📋 目录

- [配置文件位置](#配置文件位置)
- [AI 配置](#ai-配置)
- [关键词和敏感词配置](#关键词和敏感词配置)
- [平台类型配置](#平台类型配置)
- [推送配置](#推送配置)
- [快速开始](#快速开始)
- [注意事项](#注意事项)
- [验证配置](#验证配置)

## 配置文件位置

所有配置文件位于：`config/` 目录

### 主要配置文件

1. **AI配置**: `config/ai_config.yaml` - AI模型配置（用于新闻重要性分析）
2. **关键词配置**: `config/frequency_words.txt` - 关键词和敏感词配置（用于新闻筛选）
3. **平台类型配置**: `config/platform_types.yaml` - 平台分类配置
4. **推送配置**: `config/notification_config.yaml` - 推送渠道配置（可选）

---

## AI 配置

### 配置文件位置

`config/ai_config.yaml`

### 配置方式

系统支持三种配置方式，优先级从高到低：

1. **环境变量**（优先级最高）
2. **配置文件** (`config/ai_config.yaml`)
3. **默认配置**

### 配置示例

```yaml
# AI API Key（必需）
api_key: "sk-your-api-key-here"

# AI 提供商（可选，默认: deepseek）
provider: "deepseek"

# AI 模型名称（可选，默认: deepseek-chat）
model: "deepseek-chat"

# API 基础URL（可选）
base_url: ""

# 请求超时时间（秒，默认: 30）
timeout: 30

# 温度参数（0.0-2.0，默认: 0.7）
temperature: 0.7

# 最大token数（默认: 500）
max_tokens: 500
```

---

## 关键词和敏感词配置

### 配置文件位置

`config/frequency_words.txt`

### 配置方式

1. 复制示例文件：
```bash
cp config/frequency_words.txt.example config/frequency_words.txt
```

2. 编辑配置文件，添加你的关键词和敏感词规则

### 配置文件格式

详细格式说明请参考 `config/frequency_words.txt.example` 文件中的注释。

主要语法：
- **普通词**：直接写入
- **`+词`**：必须词（所有必须词都要匹配）
- **`!词`**：过滤词（匹配则排除）
- **`@数字`**：该词组最多显示的条数
- **`/pattern/`**：正则表达式
- **`词 => 显示名称`**：显示别名
- **`[别名]`**：组别名

### 区域划分

- **`[GLOBAL_FILTER]`**：全局过滤词区域
- **`[WORD_GROUPS]`**：关键词组区域（默认）

### 环境变量配置

可以通过环境变量指定配置文件路径：

```bash
export FREQUENCY_WORDS_PATH="/path/to/frequency_words.txt"
```

---

## 平台类型配置

### 配置文件位置

`config/platform_types.yaml`

### 配置说明

定义哪些平台属于论坛（forum），哪些属于新闻（news）。

```yaml
forums:
  - v2ex
  - zhihu
  - weibo
  - hupu
  - tieba
  - douyin
  - bilibili
  - nowcoder
  - juejin
  - douban

news:
  - zaobao
  - 36kr
  - toutiao
  - ithome
  - thepaper
  - cls
  - tencent
  - sspai
```

如果配置文件不存在，系统会使用默认配置。

---

## 推送配置

### 配置文件位置

`config/notification_config.yaml`

### 配置方式

1. 复制示例文件：
```bash
cp config/notification_config.yaml.example config/notification_config.yaml
```

2. 编辑配置文件，填入你的推送渠道配置

### 支持的推送渠道

- **飞书 (Feishu)**: 配置 `FEISHU_WEBHOOK_URL`
- **钉钉 (DingTalk)**: 配置 `DINGTALK_WEBHOOK_URL`
- **企业微信 (WeCom)**: 配置 `WEWORK_WEBHOOK_URL`
- **Telegram**: 配置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`
- **邮件 (Email)**: 配置 `EMAIL_FROM`, `EMAIL_PASSWORD`, `EMAIL_TO`
- **ntfy**: 配置 `NTFY_SERVER_URL` 和 `NTFY_TOPIC`
- **Bark**: 配置 `BARK_URL`
- **Slack**: 配置 `SLACK_WEBHOOK_URL`
- **通用 Webhook**: 配置 `GENERIC_WEBHOOK_URL`

### 配置示例

```yaml
# 飞书
FEISHU_WEBHOOK_URL: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 钉钉
DINGTALK_WEBHOOK_URL: "https://oapi.dingtalk.com/robot/send?access_token=xxx"

# 企业微信
WEWORK_WEBHOOK_URL: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"

# Telegram
TELEGRAM_BOT_TOKEN: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
TELEGRAM_CHAT_ID: "123456789"

# 邮件
EMAIL_FROM: "sender@example.com"
EMAIL_PASSWORD: "your-password"
EMAIL_TO: "receiver@example.com"

# ntfy
NTFY_SERVER_URL: "https://ntfy.sh"
NTFY_TOPIC: "your-topic"

# Bark
BARK_URL: "https://api.day.app/your-key"

# Slack
SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/xxx"

# 通用 Webhook
GENERIC_WEBHOOK_URL: "https://your-webhook-url.com"
```

### 多账号支持

所有渠道都支持多账号配置，使用 `;` 分隔多个 URL：

```yaml
FEISHU_WEBHOOK_URL: "url1;url2;url3"
```

### 环境变量配置

也可以通过环境变量配置推送渠道，环境变量会覆盖配置文件中的设置。

---

## 注意事项

1. **API Key安全**：
   - `ai_config.yaml` 包含敏感信息，已添加到 `.gitignore`，请勿提交到版本控制系统
   - `notification_config.yaml` 包含推送渠道密钥，已添加到 `.gitignore`，请勿提交到版本控制

2. **关键词配置**：`frequency_words.txt` 可能包含敏感词，已添加到 `.gitignore`，建议不提交到版本控制

3. **配置文件路径**：
   - AI配置：可以通过环境变量 `AI_CONFIG_PATH` 指定自定义路径
   - 关键词配置：可以通过环境变量 `FREQUENCY_WORDS_PATH` 指定自定义路径

4. **环境变量优先级**：环境变量会覆盖配置文件中的设置

5. **配置文件不存在**：如果配置文件不存在，系统会使用默认配置并尝试从环境变量读取

6. **推送配置**：推送功能是可选的，如果不配置推送渠道，系统仍可正常运行，只是不会发送推送通知

---

## 验证配置

启动服务后，查看日志输出：

### AI配置
```
[配置] 已加载AI配置: /path/to/config/ai_config.yaml
```

### 关键词配置
如果配置加载失败，会显示：
```
[警告] 关键词配置文件不存在: /path/to/config/frequency_words.txt，使用空配置
```

### 平台类型配置
如果配置加载失败，会显示：
```
[警告] 平台类型配置文件不存在: /path/to/config/platform_types.yaml
```

---

## 快速开始

1. **复制示例配置文件**：
```bash
# AI配置（必需，用于新闻重要性分析）
cp config/ai_config.yaml.example config/ai_config.yaml
# 编辑 config/ai_config.yaml，填入你的 API Key

# 关键词配置（可选，用于新闻筛选）
cp config/frequency_words.txt.example config/frequency_words.txt
# 编辑 config/frequency_words.txt，添加你的关键词规则

# 推送配置（可选，用于推送通知）
cp config/notification_config.yaml.example config/notification_config.yaml
# 编辑 config/notification_config.yaml，配置推送渠道
```

2. **编辑配置文件**，填入你的配置信息

3. **重启服务**，配置会自动加载

## 相关文档

- [README.md](../README.md) - 项目主文档
- [DOCKER.md](../DOCKER.md) - Docker 部署指南
- [CONTRIBUTING.md](../CONTRIBUTING.md) - 贡献指南
