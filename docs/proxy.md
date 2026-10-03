# 代理环境下的 WebSocket 说明

## 问题

`lark-oapi` SDK 的 WebSocket 连接默认禁用代理发现：如果你的主机只能经 HTTP(S) 代理出网，监听器会连不上飞书，而且失败时非常静默。

根因在 SDK 源码 `lark_oapi/ws/client.py`：

```python
def _ws_connect_kwargs():
    return {"proxy": None}   # ← 把 websockets 的代理发现掐死了
```

`proxy=None` 会覆盖 `websockets` 库默认的"从环境变量发现代理"行为。

## 修复

把该函数改成返回空 dict，让 `websockets` 走默认的环境变量代理发现：

```python
def _ws_connect_kwargs():
    # Allow websockets to discover proxy from environment
    # (the SDK's default of proxy=None breaks in proxied environments).
    return {}
```

然后在运行监听器的环境里导出代理变量：

```bash
export HTTPS_PROXY=http://your-proxy:3128
export HTTP_PROXY=http://your-proxy:3128
# 大小写都导出，某些库只认大写
export https_proxy=$HTTPS_PROXY http_proxy=$HTTP_PROXY
```

## 注意事项

- 这是直接改 `site-packages` 里的 SDK 文件，**每次升级/重装 `lark-oapi` 后都要重新打一遍**。建议把这段记进你的部署 checklist。
- 更干净的长期方案是给上游提 PR / 用 monkey-patch（在 `import lark_oapi.ws.client` 后覆盖 `_ws_connect_kwargs`），避免改 site-packages。
- REST 部分（`requests`）默认就认环境变量代理，不需要 patch。
