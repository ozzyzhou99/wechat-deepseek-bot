# Safe Integration Guide / 安全接入指南

## 中文

本公开版本没有平台客户端适配器。仅在独立的私有项目中，使用平台官方 API 或书面授权的接口实现 `WeChatTransport` 协议。

接入器应当：

1. 只接收已获授权的事件和频道；不枚举联系人、群组或历史消息。
2. 仅处理当前事件中必要的字段；不要读取客户端内存、文件、数据库、令牌或会话信息。
3. 默认不保存聊天内容；如确有必要，使用最短保存期、加密存储和访问控制。
4. 在向外部 LLM 提交任何消息前，执行成员告知、必要的同意/授权检查和敏感信息过滤。
5. 提供停止、删除和导出/访问请求的处理路径，并记录安全事件而不记录聊天正文或凭据。

不得通过注入、Hook、自动化操控客户端、抓取、逆向工程、规避安全措施或未经授权的第三方工具接入平台。

## English

This public release includes no platform-client adapter. Implement `WeChatTransport` only in a separate private integration using an official API or a specifically authorised interface.

An adapter should accept only authorised events and channels, process only fields needed for the current event, avoid client memory/files/databases/tokens/session data, keep archiving off by default, minimise and protect any necessary data, and check notice/consent or another lawful basis before sending content to an external LLM.

Do not use injection, hooking, client automation, scraping, reverse engineering, security-measure circumvention, or unauthorised third-party tools to access a platform.
