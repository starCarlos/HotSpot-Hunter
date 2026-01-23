# 推送功能使用指南

本文档介绍 HotSpot Hunter 的推送通知功能，包括支持的推送渠道、配置方法和使用示例。

## 📋 目录

- [支持的推送渠道](#支持的推送渠道)
- [配置方法](#配置方法)
- [使用方法](#使用方法)
- [多账号支持](#多账号支持)
- [故障排查](#故障排查)
- [注意事项](#注意事项)

## 支持的推送渠道

HotSpot Hunter 支持以下推送渠道：

- **飞书 (Feishu)**: 企业协作平台
- **钉钉 (DingTalk)**: 企业通讯平台
- **企业微信 (WeCom/WeWork)**: 企业微信机器人
- **Telegram**: 即时通讯应用
- **邮件 (Email)**: SMTP 邮件服务
- **ntfy**: 开源推送服务
- **Bark**: iOS 推送服务
- **Slack**: 团队协作平台
- **通用 Webhook**: 自定义 Webhook 接口

## 配置方法

### 1. 复制配置文件

```bash
cp config/notification_config.yaml.example config/notification_config.yaml
```

### 2. 编辑配置文件

编辑 `config/notification_config.yaml`，填入你的推送渠道配置：

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

### 3. 获取推送渠道配置

#### 飞书

1. 打开飞书，进入需要推送的群聊
2. 点击群设置 → 群机器人 → 添加机器人 → 自定义机器人
3. 设置机器人名称和描述
4. 复制 Webhook 地址

#### 钉钉

1. 打开钉钉，进入需要推送的群聊
2. 点击群设置 → 智能群助手 → 添加机器人 → 自定义
3. 设置机器人名称
4. 复制 Webhook 地址和加签密钥（如需要）

#### 企业微信

1. 打开企业微信，进入需要推送的群聊
2. 点击群设置 → 群机器人 → 添加机器人
3. 设置机器人名称
4. 复制 Webhook 地址

#### Telegram

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取 Bot Token
5. 在 Telegram 中找到 `@userinfobot`，获取你的 Chat ID

#### 邮件

使用支持 SMTP 的邮箱服务，如 Gmail、QQ 邮箱等。部分邮箱需要开启"授权码"功能。

#### ntfy

1. 访问 [ntfy.sh](https://ntfy.sh) 或搭建自己的 ntfy 服务器
2. 选择一个主题（Topic）名称
3. 配置服务器 URL 和主题名称

#### Bark

1. 在 iOS 设备上安装 Bark 应用
2. 打开应用，复制推送 URL

#### Slack

1. 进入 Slack 工作区
2. 访问 https://api.slack.com/apps
3. 创建新应用或选择现有应用
4. 启用 Incoming Webhooks
5. 创建 Webhook URL

## 使用方法

### 在代码中使用

```python
from app.notification import NotificationDispatcher
from datetime import datetime
from app.utils.notification_config_loader import load_notification_config

# 加载配置
config = load_notification_config()

# 创建调度器
dispatcher = NotificationDispatcher(
    config=config,
    get_time_func=datetime.now,
    split_content_func=lambda content, size: [content[i:i+size] for i in range(0, len(content), size)]
)

# 准备报告数据
report_data = {
    "stats": [...],  # 统计数据
    "new_titles": [...],  # 新增标题
    "failed_ids": [...],  # 失败的平台ID
    "id_to_name": {...},  # ID到名称映射
}

# 发送通知
results = dispatcher.dispatch_all(
    report_data=report_data,
    report_type="当日汇总",
    mode="daily",
    html_file_path="path/to/report.html",  # 邮件使用
)

# 检查结果
for channel, success in results.items():
    print(f"{channel}: {'✅' if success else '❌'}")
```

### 推送内容格式

推送内容会根据不同渠道自动格式化：

- **飞书/钉钉**: 使用富文本卡片格式
- **企业微信/Telegram/ntfy/Bark/Slack**: 使用 Markdown 格式
- **邮件**: 支持 HTML 格式（如果提供了 HTML 文件）

## 多账号支持

所有渠道都支持多账号配置，使用 `;` 分隔多个 URL：

```yaml
FEISHU_WEBHOOK_URL: "url1;url2;url3"
```

系统会自动向所有配置的账号发送推送。

## 故障排查

### 推送失败

1. **检查配置是否正确**
   - 确认 Webhook URL 或 Token 是否正确
   - 检查配置文件格式是否正确

2. **检查网络连接**
   - 确认服务器可以访问推送服务
   - 检查防火墙设置

3. **查看日志**
   - 查看控制台错误信息
   - 检查推送服务的错误响应

### 常见错误

- **401 Unauthorized**: 认证失败，检查 Token 或 Webhook URL
- **403 Forbidden**: 权限不足，检查机器人权限设置
- **404 Not Found**: URL 错误，检查 Webhook 地址
- **429 Too Many Requests**: 请求过于频繁，等待后重试

### 邮件发送问题

1. **SMTP 配置错误**
   - 检查 SMTP 服务器地址和端口
   - 确认是否需要 SSL/TLS

2. **授权码问题**
   - 部分邮箱需要使用授权码而非密码
   - 检查是否开启了"允许第三方应用"

## 注意事项

1. **配置文件安全**
   - `config/notification_config.yaml` 包含敏感信息，已添加到 `.gitignore`
   - 不要将配置文件提交到版本控制

2. **依赖检查**
   - 确保已安装所有依赖：`pip install -r requirements.txt`
   - 邮件功能需要 Python 标准库 `smtplib`（通常已包含）

3. **错误处理**
   - 所有发送函数都有错误处理
   - 失败时会打印错误信息，但不会中断程序

4. **批次发送**
   - 大内容会自动分批发送
   - 可通过配置调整批次大小和间隔

5. **推送频率**
   - 注意各推送服务的频率限制
   - 避免过于频繁的推送导致账号被封

## 相关文档

- [config/README.md](config/README.md) - 配置说明
- [README.md](README.md) - 项目主文档
- [DOCKER.md](DOCKER.md) - Docker 部署指南
