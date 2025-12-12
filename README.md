## 批量邮件发送小工具（Gmail / 飞书邮箱）

一个简单的 Flask 网页工具，支持：

- 通过浏览器上传 CSV
- 选择发件账号（Gmail / 飞书邮箱）
- 使用模板批量发送邮件

### 1. 安装依赖

在项目根目录下：

```bash
cd bulk_email_tool
python -m venv .venv
source .venv/bin/activate  # Windows 使用: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

可以在 `bulk_email_tool` 目录下创建 `.env` 文件，示例：

```env
APP_SECRET_KEY=some-random-secret

# 全局发送节奏（秒），防止过快被判定为垃圾邮件
EMAIL_SEND_DELAY_SECONDS=2.0

########################
# Gmail 账号配置示例
########################

GMAIL_SMTP_USER=your_gmail_address@gmail.com
GMAIL_SMTP_PASSWORD=your_app_password   # 推荐使用应用专用密码
GMAIL_SMTP_HOST=smtp.gmail.com
GMAIL_SMTP_PORT=587
GMAIL_SMTP_USE_TLS=true
GMAIL_SMTP_USE_SSL=false
GMAIL_SENDER_NAME=Your Name

########################
# 飞书邮箱账号配置示例
########################

FEISHU_SMTP_USER=your_feishu_email@example.com
FEISHU_SMTP_PASSWORD=your_password_or_app_token
FEISHU_SMTP_HOST=smtp.feishu.cn
FEISHU_SMTP_PORT=587
FEISHU_SMTP_USE_TLS=true
FEISHU_SMTP_USE_SSL=false
FEISHU_SENDER_NAME=Your Name
```

> 注意：请确保使用合法授权的邮箱账号，并遵守公司和邮件服务商的反垃圾邮件策略。

### 3. 启动服务

开发环境本地运行：

```bash
cd bulk_email_tool
source .venv/bin/activate
python app.py
```

浏览器访问：`http://127.0.0.1:5000/`

部署到服务器时，可以用 `gunicorn` / `uwsgi` 等方式托管 Flask，并通过 Nginx 做反向代理。

### 4. CSV 格式说明

推荐的 CSV 表头：

- `email`（必需）：收件人邮箱
- `name`（可选）：收件人姓名
- `subject`（可选）：该行独立标题（若空则使用表单里的标题）
- `body`（可选）：该行独立正文（若空则使用正文模板）

示例：

```csv
email,name
user1@example.com,Alice
user2@example.com,Bob
```

### 5. 模板占位符

在网页表单里的“邮件正文模板”中，可以使用：

- `$name`：来自 CSV 的 `name` 列
- `$email`：来自 CSV 的 `email` 列
- 其它列：例如 CSV 里有 `company` 列，则可以写 `$company`

如果某一行在 CSV 中包含 `body` 列，则该行会直接使用 `body` 的内容，不再套用模板。

### 6. 给同事使用的方式

- 技术同事负责在服务器上部署本工具，并配置 Gmail / 飞书邮箱账号的环境变量。
- 将访问地址（例如公司内网域名）发给需要群发邮件的同事。
- 同事只需要准备好 CSV、在网页选择账号并上传即可发送，不需要接触账号密码。

