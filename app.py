import csv
import io
import os
import time
from email.mime.text import MIMEText
from email.utils import formataddr
from string import Template

import smtplib
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "change-this-secret")


def _str_to_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


SEND_DELAY_SECONDS = float(os.getenv("EMAIL_SEND_DELAY_SECONDS", "2.0"))


ACCOUNT_DEFAULTS = {
    "gmail": {
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True,
        "use_ssl": False,
    },
    "feishu": {
        "host": "smtp.feishu.cn",
        "port": 587,
        "use_tls": True,
        "use_ssl": False,
    },
}


def load_account_config(
    account_name: str,
    user_override: str | None = None,
    password_override: str | None = None,
) -> dict:
    account_name = account_name.lower()
    if account_name not in ACCOUNT_DEFAULTS:
        raise ValueError(f"Unknown account: {account_name}")

    prefix = account_name.upper()
    defaults = ACCOUNT_DEFAULTS[account_name]

    env_user = os.getenv(f"{prefix}_SMTP_USER")
    env_password = os.getenv(f"{prefix}_SMTP_PASSWORD")

    user = (user_override or "").strip() or env_user
    password = (password_override or "").strip() or env_password

    if not user or not password:
        raise RuntimeError(
            f"Missing credentials for {account_name}. "
            f"Please either provide email and password on the page "
            f"or set {prefix}_SMTP_USER and {prefix}_SMTP_PASSWORD."
        )

    host = os.getenv(f"{prefix}_SMTP_HOST", defaults["host"])
    port = int(os.getenv(f"{prefix}_SMTP_PORT", str(defaults["port"])))
    use_tls = _str_to_bool(
        os.getenv(f"{prefix}_SMTP_USE_TLS"), defaults["use_tls"]
    )
    use_ssl = _str_to_bool(
        os.getenv(f"{prefix}_SMTP_USE_SSL"), defaults["use_ssl"]
    )
    sender_name = os.getenv(f"{prefix}_SENDER_NAME", user)

    return {
        "name": account_name,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "sender_name": sender_name,
    }


def send_batch_emails(account: dict, messages: list[dict]) -> tuple[list[dict], list[dict]]:
    success = []
    failed = []

    if account["use_ssl"]:
        server_cls = smtplib.SMTP_SSL
    else:
        server_cls = smtplib.SMTP

    with server_cls(account["host"], account["port"]) as server:
        server.ehlo()
        if account["use_tls"] and not account["use_ssl"]:
            server.starttls()
            server.ehlo()
        server.login(account["user"], account["password"])

        for item in messages:
            msg = MIMEText(item["body"], "plain", "utf-8")
            msg["From"] = formataddr((account["sender_name"], account["user"]))
            msg["To"] = item["to_email"]
            msg["Subject"] = item["subject"]

            try:
                server.sendmail(
                    account["user"],
                    [item["to_email"]],
                    msg.as_string(),
                )
                success.append(item)
            except Exception as exc:  # noqa: BLE001
                item_with_error = dict(item)
                item_with_error["error"] = str(exc)
                failed.append(item_with_error)
            time.sleep(SEND_DELAY_SECONDS)

    return success, failed


def parse_csv(file_storage) -> list[dict]:
    raw = file_storage.read()
    if not raw:
        raise ValueError("CSV 文件为空")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # 兼容部分中文环境导出的 GBK/GB2312
        text = raw.decode("gbk", errors="ignore")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for row in reader:
        normalized = {}
        for key, value in row.items():
            if key is None:
                continue
            normalized[key.strip().lower()] = (value or "").strip()

        email = normalized.get("email")
        if not email:
            continue
        rows.append(normalized)

    if not rows:
        raise ValueError("CSV 中没有有效的 email 行")

    return rows


@app.route("/", methods=["GET"])
def index():
    accounts = ["gmail", "feishu"]
    return render_template("upload.html", accounts=accounts)


@app.route("/send", methods=["POST"])
def send():
    account_name = request.form.get("account", "gmail")
    smtp_user = (request.form.get("smtp_user") or "").strip()
    smtp_password = (request.form.get("smtp_password") or "").strip()
    subject_template_str = (request.form.get("subject") or "").strip()
    body_template_str = (request.form.get("body_template") or "").strip()

    file = request.files.get("file")

    if not file or file.filename == "":
        flash("请上传 CSV 文件", "error")
        return redirect(url_for("index"))

    try:
        account = load_account_config(
            account_name,
            user_override=smtp_user or None,
            password_override=smtp_password or None,
        )
    except Exception as exc:  # noqa: BLE001
        flash(str(exc), "error")
        return redirect(url_for("index"))

    try:
        rows = parse_csv(file)
    except Exception as exc:  # noqa: BLE001
        flash(f"解析 CSV 失败: {exc}", "error")
        return redirect(url_for("index"))

    subject_template = Template(subject_template_str or "")
    body_template = Template(body_template_str or "")

    messages = []
    for row in rows:
        email = row.get("email")
        if not email:
            continue

        to_name = row.get("name", "")
        context = dict(row)
        context.setdefault("name", to_name)
        context.setdefault("email", email)

        if subject_template_str:
            row_subject = subject_template.safe_substitute(context)
        else:
            row_subject = (row.get("subject") or "").strip() or "无标题"

        if row.get("body"):
            body = row["body"]
        else:
            body = body_template.safe_substitute(context)

        messages.append(
            {
                "to_email": email,
                "to_name": to_name,
                "subject": row_subject,
                "body": body,
            }
        )

    if not messages:
        flash("没有可发送的邮件行", "error")
        return redirect(url_for("index"))

    success, failed = send_batch_emails(account, messages)

    return render_template(
        "result.html",
        account_name=account_name,
        total=len(messages),
        success=success,
        failed=failed,
    )


if __name__ == "__main__":
    # 本地开发直接运行：python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
