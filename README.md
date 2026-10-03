# feishu-agent-bridge

让任意 AI agent（Muse、dot、cue，或你自己的 bot）在飞书里拥有一个原生身份：收到 @提及、发出回复，全程不依赖第三方中转。

> **通用方案，不绑定任何特定 agent 框架。** 仓库里没有任何账号密码——所有凭证都通过环境变量注入。

## 它能做什么

- **发消息**：`scripts/feishu_send.py --chat <chat_id> --text "..."`，以你的飞书应用身份向指定群聊发送文本消息。
- **收消息**：`scripts/feishu_listen.py` 通过 WebSocket 长连接监听 `im.message.receive_v1` 事件；被 @ 时自动打一个 OK 表情（可见的"已收到"标记），并把消息写入 `mention_queue.jsonl` 交给你的 agent 消费；没被 @ 时保持静默。
- **鉴权**：用 App ID / App Secret 换取 `tenant_access_token`（约 2 小时有效，脚本内自动缓存、提前刷新）。
- **代理环境**：支持经 HTTP(S) 代理出网；WebSocket 部分需要给 `lark-oapi` SDK 打一个小 patch（见 `docs/proxy.md`）。

## 前置条件

1. 在[飞书开放平台](https://open.feishu.cn/)创建一个企业自建应用，拿到 **App ID**（`cli_` 开头）和 **App Secret**。
2. 给应用开通权限：获取 `tenant_access_token` 的鉴权权限、`im:message`（接收消息事件）、`im:message:send_as_bot`（以应用身份发消息）。如果要用 OK 表情做已读标记，再加 reactions 相关权限。
3. 事件订阅选择 **长连接（WebSocket）**，订阅 `im.message.receive_v1`，然后发布应用版本。
4. 把应用（机器人）拉进要使用的群聊。
5. Python 3.8+，`pip install -r requirements.txt`（**必须装到运行监听器的那个 Python 环境里**，装错环境是最常见的坑）。

## 快速开始

```bash
cp examples/.env.example .env   # 填入你自己的 App ID / App Secret
export $(cat .env | xargs)       # 或用你习惯的方式注入环境变量

# 发一条消息
python3 scripts/feishu_send.py --chat oc_xxxxxxxx --text "你好，我是你的 agent"

# 启动监听（被 @ 时写入 mention_queue.jsonl）
python3 scripts/feishu_listen.py
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `FEISHU_APP_ID` | 是 | 飞书应用 App ID（`cli_` 开头） |
| `FEISHU_APP_SECRET` | 是 | 飞书应用 App Secret |
| `BOT_NAME` | 否 | 机器人显示名，用于 @提及 的名字兜底匹配 |
| `BOT_OPEN_ID` | 否 | 机器人在本应用下的 `open_id`，提及精确匹配（推荐配置） |
| `TARGET_CHAT` | 否 | 只处理指定群聊；为空则任意群聊里的 @ 都处理 |
| `QUEUE_PATH` | 否 | 提及转交队列路径（默认 `./mention_queue.jsonl`） |
| `HEARTBEAT_PATH` | 否 | 心跳文件路径（默认 `./listener_heartbeat.txt`） |
| `HTTPS_PROXY` / `HTTP_PROXY` | 否 | 出网代理；WebSocket 需配合 SDK patch（见 `docs/proxy.md`） |

## 推荐的消息流

```
飞书群里 @你的机器人
  → feishu_listen.py（WS 长连接）→ 打 OK 表情 → 写入 mention_queue.jsonl
  → 你的 agent（Muse / dot / cue……）消费队列 → 生成回复
  → feishu_send.py --chat <来源群> --text "回复"（必须回在 @ 发生的群里，不硬编码）
```

几条保命原则：

- 一个 App ID 只跑 **一个** WebSocket 连接（飞书把事件路由到单连接，多开会丢事件）。
- 回复永远发到 @ 发生的来源群。
- 凭证只出现在进程环境变量里，绝不写进代码、日志和仓库。

## 文档

- `SKILL.md`：给 agent 读的接入 playbook，照着一步一步做就能跑起来。
- `docs/proxy.md`：代理环境下 WebSocket 的 SDK patch 说明。
- `docs/supervision.md`：用心跳文件做看门狗，监听器挂了自动拉起。

## 安全

本仓库不含任何真实凭证、App ID、群聊 ID。`.env` 已在 `.gitignore` 中，提交前请再扫一遍。

## License

MIT
