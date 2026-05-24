from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from . import __version__
from .core import fetch_mail_items, mail_to_dict, parse_combo

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html", version=__version__)


@app.get("/health")
def health():
    return jsonify(ok=True, version=__version__)


@app.post("/api/fetch")
def api_fetch():
    try:
        payload = request.get_json(force=True) or {}
        account = parse_combo(str(payload.get("combo") or ""))
        limit = max(1, min(int(payload.get("limit") or 10), 100))
        keyword = str(payload.get("keyword") or "").strip()
        mails, rotated_token = fetch_mail_items(account, limit=limit, keyword=keyword)
        return jsonify(
            ok=True,
            mails=[mail_to_dict(m) for m in mails],
            code_count=sum(len(m.codes) for m in mails),
            summary=f"读取完成：返回 {len(mails)} 封邮件，识别 {sum(len(m.codes) for m in mails)} 个候选验证码。",
            refresh_token_rotated=bool(rotated_token),
            new_refresh_token=rotated_token,
        )
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8765"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
