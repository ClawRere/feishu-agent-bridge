---
name: "feishu-agent-bridge"
description: "Give any AI agent (Muse, dot, cue, or your own bot) a native Feishu identity: receive @mentions over WebSocket and send replies. Credentials via env vars only, never in files."
---

# Feishu Agent Bridge — 接入 Playbook

目标：让一个 AI agent 在飞书里拥有原生身份，能收 @提及、能回消息。本 playbook 适用于任何 agent（Muse、dot、cue、自研 bot），按顺序执行即可。

## 1. 创建飞书应用

- 在飞书开放平台创建企业自建应用，记下 **App ID**（`cli_` 开头）和 **App Secret**。
- 开通权限：获取 `tenant_access_token` 的鉴权权限、`im:message`（接收消息事件）、`im:message:send_as_bot`（以应用身份发消息）；如需 OK 表情已读标记，加 reactions 相关权限。
- 事件订阅选 **长连接（WebSocket）**，订阅 `im.message.receive_v1`，发布应用版本。
- 把机器人拉进目标群聊。

## 2. 运行环境

- Python 3.8+；`pip install -r requirements.txt`，**必须装到运行监听器的那个 Python 环境**（`python3 -c "import lark_oapi"` 验证）。
- 凭证只通过环境变量注入：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`。绝不写进代码、日志、仓库。

## 3. 鉴权

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
Content-Type: application/json
{"app_id": "<APP_ID>", "app_secret": "<APP_SECRET>"}
→ {"tenant_access_token": "..."}   # 约 2 小时有效，缓存并提前刷新
```

仓库脚本内已实现缓存逻辑，直接调用即可。

## 4. 接收：WebSocket 监听

- `scripts/feishu_listen.py`：单个 `lark_oapi.ws.Client`，注册 `p2_im_message_receive_v1`。
- **一个 App ID 只跑一个连接**——飞书把事件路由到单连接，多开会丢事件。
- 回调里解析 `event.message.content`（JSON，取 `text` 字段），检查 `event.message.mentions`：
  - `mentioned_type` 为 `bot`/`app` 且 `open_id` 等于 `BOT_OPEN_ID`（或名字等于 `BOT_NAME`）→ 确认被 @。
- 被 @ 时：① 给该消息打 OK 表情（可见的"已收到"）；② 把消息以 JSONL 追加到 `QUEUE_PATH`，交下游 agent 处理。没被 @ 时保持静默。
- 按 `message_id` 去重；每 ~30s 写一次心跳文件。
- 代理环境：参考 `docs/proxy.md` 给 SDK 打 patch，否则 WS 连不上。

## 5. 发送：REST

```
POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id
Authorization: Bearer <tenant_access_token>
{"receive_id": "<chat_id，如 oc_...>", "msg_type": "text",
 "content": "{\"text\": \"...\"}"}
```

- 成功返回 `code: 0` 和 `data.message_id`；其他 code 都是失败——把原因打出来，不要盲重试。
- `scripts/feishu_send.py --chat <chat_id> --text "..."` 已封装好。

## 6. 守护

- 看门狗读心跳文件（`HEARTBEAT_PATH`）：超过 ~90s 没更新或进程消失 → 用同一个 Python 环境、同一套环境变量重启监听器。
- 参考 `docs/supervision.md` 的 systemd 模板 / nohup 方案。

## 7. 通道健康原则

- 凭证只在用户给定时、当次、以环境变量形式出现——不进文件、不进日志、不进代码。
- 一个 App ID 一个 WS 连接。
- 回复永远发到 @ 发生的来源群，不硬编码群 ID。
