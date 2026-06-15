# 服务器部署说明

以下示例适用于 Ubuntu 22.04/24.04 + Python 3 + Gunicorn + Nginx。

## 1. 拉取代码

```bash
cd /opt
git clone <你的 GitHub 仓库地址> kaoshi
cd /opt/kaoshi
```

## 2. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 设置环境变量

```bash
export SECRET_KEY="请替换为足够长的随机密钥"
```

也可以把环境变量写入 systemd 服务文件。

## 4. 初始化运行

```bash
source .venv/bin/activate
gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
```

浏览器通过服务器反向代理访问后，默认管理员账号：

- 账号：`admin`
- 密码：`admin123`

首次上线后请尽快修改默认管理员密码。

## 5. systemd 服务示例

保存为 `/etc/systemd/system/kaoshi.service`：

```ini
[Unit]
Description=Material Exam System
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/kaoshi
Environment="SECRET_KEY=请替换为足够长的随机密钥"
ExecStart=/opt/kaoshi/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kaoshi
sudo systemctl status kaoshi
```

## 6. Nginx 反向代理示例

```nginx
server {
    listen 80;
    server_name 你的域名或服务器 IP;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 数据文件

运行数据默认保存到：

```text
data/exam_system.sqlite3
```

该目录不提交到 GitHub。上线后请定期备份 `data/` 目录。
