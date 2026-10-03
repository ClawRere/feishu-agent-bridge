# 监听器守护：心跳 + 看门狗

`scripts/feishu_listen.py` 每 ~30s（`HEARTBEAT_INTERVAL`）往 `HEARTBEAT_PATH` 写一次当前时间戳。看门狗只需要做一件事：心跳过期（>90s 没更新）或进程消失 → 用**同一个 Python 环境、同一套环境变量**重启监听器。

## 方案 A：systemd（推荐，Linux）

`/etc/systemd/system/feishu-listener.service`（把占位符换成你的真实路径/用户）：

```ini
[Unit]
Description=Feishu agent listener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/opt/feishu-agent-bridge
Environment=FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
Environment=FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# 代理环境才需要下面四行
Environment=HTTPS_PROXY=http://your-proxy:3128
Environment=HTTP_PROXY=http://your-proxy:3128
Environment=https_proxy=http://your-proxy:3128
Environment=http_proxy=http://your-proxy:3128
ExecStart=/opt/feishu-agent-bridge/venv/bin/python /opt/feishu-agent-bridge/scripts/feishu_listen.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now feishu-listener
```

注意：`Environment=` 里写的是**你的真实凭证**，这个 unit 文件不要进任何仓库。

## 方案 B：极简看门狗（cron 每 5 分钟）

```bash
#!/usr/bin/env bash
# 心跳超过 120s 则重启监听器
HB=/opt/feishu-agent-bridge/listener_heartbeat.txt
NOW=$(date +%s)
LAST=$(cat "$HB" 2>/dev/null || echo 0)
LAST=${LAST%.*}  # 去掉小数
if [ $((NOW - LAST)) -gt 120 ] || ! pgrep -f "[f]eishu_listen.py" >/dev/null; then
  pkill -f "[f]eishu_listen.py"
  # 用运行监听器的那个 Python，并带上同样的环境变量
  export FEISHU_APP_ID=... FEISHU_APP_SECRET=...
  nohup /opt/feishu-agent-bridge/venv/bin/python /opt/feishu-agent-bridge/scripts/feishu_listen.py \
    >> /opt/feishu-agent-bridge/listener.log 2>&1 &
fi
```

`pkill` 时用 `[f]eishu_listen.py` 的字符类写法——直接 `pkill -f "feishu_listen.py"` 会把执行 pkill 的 shell 自己也匹配进去杀掉。

## 提醒

- 重启必须用**同一个 venv 的 python**（装了 `lark-oapi` 的那个），否则 `import lark_oapi` 失败。
- 代理环境下重启时别忘了带上代理环境变量，否则 WS 重连失败。
