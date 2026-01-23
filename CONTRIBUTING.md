# 贡献指南

感谢你对 HotSpot Hunter 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告 Bug

如果你发现了 Bug，请通过以下方式报告：

1. 在 [Issues](https://github.com/starCarlos/HotSpot-Hunter/issues) 中搜索是否已有相关问题
2. 如果没有，创建一个新的 Issue
3. 在 Issue 中提供：
   - 清晰的 Bug 描述
   - 复现步骤
   - 期望的行为
   - 实际的行为
   - 环境信息（Python 版本、操作系统等）
   - 相关的日志或错误信息

### 提出新功能

如果你有好的想法或建议：

1. 在 [Issues](https://github.com/starCarlos/HotSpot-Hunter/issues) 中搜索是否已有类似建议
2. 创建一个新的 Issue，使用 "Feature Request" 标签
3. 详细描述：
   - 功能需求
   - 使用场景
   - 可能的实现方案（如果有）

### 提交代码

#### 开发流程

1. **Fork 仓库**
   ```bash
   # 在 GitHub 上 Fork 本项目
   ```

2. **克隆你的 Fork**
   ```bash
   git clone https://github.com/starCarlos/HotSpot-Hunter.git
   cd HotSpot-Hunter
   ```

3. **创建开发分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

4. **进行开发**
   - 编写代码
   - 添加必要的注释和文档字符串
   - 确保代码符合 PEP 8 规范
   - 添加必要的测试（如果适用）

5. **提交更改**
   ```bash
   git add .
   git commit -m "描述你的更改"
   ```
   
   提交信息规范：
   - 使用清晰、简洁的描述
   - 如果是修复 Bug，以 `fix:` 开头
   - 如果是新功能，以 `feat:` 开头
   - 如果是文档更新，以 `docs:` 开头

6. **推送更改**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **创建 Pull Request**
   - 在 GitHub 上创建 Pull Request
   - 填写 PR 描述，说明：
     - 更改的内容
     - 为什么需要这个更改
     - 如何测试
   - 等待代码审查

#### 代码规范

- **Python 代码风格**: 遵循 PEP 8
- **类型注解**: 尽量使用类型注解
- **文档字符串**: 为函数和类添加文档字符串
- **注释**: 为复杂逻辑添加注释
- **命名**: 使用有意义的变量和函数名

示例：
```python
def fetch_news(platform_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    从指定平台抓取新闻
    
    Args:
        platform_id: 平台ID
        limit: 返回数量限制
        
    Returns:
        新闻数据列表
    """
    # 实现代码
    pass
```

#### 测试

在提交 PR 之前，请确保：

1. 代码可以正常运行
2. 没有引入新的错误
3. 如果修改了 API，确保 API 文档仍然正确
4. 如果添加了新功能，添加相应的测试（如果适用）

### 改进文档

文档的改进同样重要：

- 修复文档中的错误
- 添加缺失的说明
- 改进文档的可读性
- 添加使用示例
- 翻译文档（如果适用）

## 开发环境设置

### 本地开发

1. **克隆仓库**
   ```bash
   git clone https://github.com/starCarlos/HotSpot-Hunter.git
   cd HotSpot-Hunter
   ```

2. **创建虚拟环境**（推荐）
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境**
   ```bash
   cp config/ai_config.yaml.example config/ai_config.yaml
   # 编辑配置文件
   ```

5. **运行开发服务器**
   ```bash
   uvicorn main:app --reload
   ```

### Docker 开发

```bash
# 使用开发配置
docker-compose -f docker-compose.dev.yml up
```

## Pull Request 检查清单

在提交 PR 之前，请确认：

- [ ] 代码遵循项目规范
- [ ] 添加了必要的注释和文档
- [ ] 没有引入新的警告或错误
- [ ] 更新了相关文档（如果适用）
- [ ] 提交信息清晰明确
- [ ] 代码已经过测试

## 代码审查

所有提交的代码都会经过审查。审查过程可能包括：

- 代码质量和风格检查
- 功能正确性验证
- 性能考虑
- 安全性检查
- 文档完整性

请耐心等待审查，并根据反馈进行修改。

## 行为准则

参与本项目时，请：

- 保持尊重和友好
- 接受建设性的批评
- 专注于对项目最有利的事情
- 尊重不同的观点和经验

## 问题反馈

如果你在贡献过程中遇到任何问题，可以：

- 在 Issues 中提问
- 查看现有文档
- 联系项目维护者

感谢你的贡献！🎉
