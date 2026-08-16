# Privacy-First Chatbot Framework / 隐私优先聊天机器人框架

[中文](#中文说明) · [English](#english)

> **Public safe edition / 公开安全版** — This repository is a transport-agnostic framework. It intentionally does **not** include DLL injection, client hooking, desktop UI automation, client-database access, scraping, session interception, or a connector to a personal WeChat account.

## 中文说明

这是一个用于构建群聊 AI 助手的 Python 框架，保留路由、短期上下文、命令、人格、内容过滤、数据最小化和本地分析等通用能力。

### 合规与安全声明

- 本仓库不提供、也不鼓励通过 DLL 注入、Hook、桌面自动化、读取客户端数据库或绕过平台措施来接入微信或其他平台。
- 接入层必须由使用者基于平台官方 API 或取得书面授权的接口自行实现；请先审阅平台条款、适用法律和组织政策。
- 默认关闭聊天归档。若启用，使用者应先以清晰方式告知所有受影响成员处理目的、数据种类、保存期限、第三方 LLM 传输及删除方式，并取得适当授权或具有其他合法处理基础。
- 不要收集超出功能所需的数据；不得提交 `.env`、真实 API Key、群 ID、账号 ID、聊天记录或日志。
- 本项目仅作技术示例，不构成法律意见，也不保证特定部署方案合规。

### 安装与配置

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

在私有 `.env` 中填写 LLM 凭据。公开仓库中的 `.env.example` 始终保持空白凭据。运行 `pytest` 可验证框架核心。

### 接入方式

公共版本不会连接任何聊天客户端。请在私有项目中实现 `WeChatTransport` 协议，并且只使用官方或明确获授权的 API。接入前请阅读 [安全接入指南](docs/SAFE_INTEGRATION.md) 和 [群成员告知模板](docs/PRIVACY_NOTICE_TEMPLATE.md)。

## English

This Python framework provides reusable building blocks for a group-chat AI assistant: routing, bounded conversation memory, commands, personas, content filtering, data minimization, and local analysis.

### Compliance and safety notice

- This repository does not distribute or endorse DLL injection, client hooking, desktop UI automation, client-database access, scraping, session interception, or connectors for personal WeChat accounts.
- You must implement the transport layer privately using a platform's official API or a separately authorized interface. Review the platform terms, applicable law, and your organisation's policy first.
- Chat archiving is disabled by default. Before enabling it, clearly notify every affected participant about the purpose, data categories, retention period, LLM transfer, and deletion route, and obtain appropriate consent or another lawful basis.
- Collect only what is necessary. Never commit `.env`, real API keys, channel identifiers, account identifiers, chat content, or logs.
- This is a technical framework, not legal advice or a guarantee that a deployment is compliant.

### Install and configure

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Put LLM credentials only in your private `.env`. The public `.env.example` contains no credentials. Run `pytest` to verify the framework core.

### Integrate safely

The public release cannot connect to a chat client. In a private integration, implement the `WeChatTransport` protocol only with an official or explicitly authorised API. Read the [safe integration guide](docs/SAFE_INTEGRATION.md) and the [participant notice template](docs/PRIVACY_NOTICE_TEMPLATE.md) first.

## Privacy checklist / 隐私检查清单

- [ ] `.env` is ignored and no secret is staged.
- [ ] Chat archives and logs are ignored and encrypted or otherwise protected locally.
- [ ] Every participant has received a clear notice before data collection begins.
- [ ] Archiving is disabled unless it is necessary and has a lawful basis.
- [ ] The deployed adapter uses an official or explicitly authorised interface.
