# Outlook RT Login 接码助手 📮

一个用于 Outlook/Hotmail 账号的轻量 Web + CLI 接码工具。输入：

```text
邮箱----密码----client_id----refresh_token
```

工具会使用 `client_id + refresh_token` 换取 Microsoft access_token，再通过 Outlook IMAP XOAUTH2 读取 `INBOX` 和 `Junk` 最新邮件，提取 4-8 位数字验证码。

Web 端支持直接粘贴多行，也支持上传 `.txt` 文件；TXT 里一行一个账号即可。

> 密码字段只是兼容账号导出格式，当前不会用于登录，也不会保存。

## 特性

- Web 页面直接输入账号串获取验证码
- 支持上传 TXT 批量读取多个邮箱（一行一个账号，单次最多 50 个）
- CLI 支持 Windows / Linux / macOS
- 同时扫描收件箱和垃圾箱
- 支持关键词过滤
- 默认不落库、不保存账号、不回显敏感 token
- 如果 Microsoft 返回新的 refresh_token，页面会生成“更新后账号 TXT”和“仅轮换账号 TXT”，方便复制或下载导出

## Linux 运行

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
HOST=0.0.0.0 PORT=8765 python -m outlook_rt_login.web
```

或：

```bash
./run-linux.sh
```

打开：`http://127.0.0.1:8765`

### TXT 批量格式

```text
email1@outlook.com----password----client_id----refresh_token
email2@outlook.com----password----client_id----refresh_token
# 以 # 开头的行会被忽略
```

批量读取后，页面会提供两个导出按钮：

- `复制/下载全部更新后账号`：已轮换账号替换为新 refresh_token，未轮换账号保留原行。
- `复制/下载只轮换账号`：只导出本次发生 refresh_token 轮换的账号。

## Windows 运行

PowerShell：

```powershell
.\run-windows.ps1
```

或双击：`run-windows.bat`

打开：`http://127.0.0.1:8765`

## Docker 运行

```bash
docker compose up -d --build
```

打开：`http://服务器IP:8765`

## CLI 用法

```bash
python -m outlook_rt_login.cli 'email@outlook.com----password----client_id----refresh_token'
python -m outlook_rt_login.cli --json -n 20 -k verification 'email@outlook.com----password----client_id----refresh_token'
```

## 安全说明

- 不要把真实账号串提交到仓库、Issue、日志或公开聊天。
- Web 版本默认不会保存输入内容；部署到公网时建议加反代鉴权或只给自己使用。
- refresh_token 可能会轮换；如果页面提示新 token，请复制替换原资料。
