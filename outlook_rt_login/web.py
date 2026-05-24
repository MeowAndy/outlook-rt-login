from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from . import __version__
from .core import fetch_mail_items, mail_to_dict, parse_combo, parse_combo_lines

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
            account=account.email,
            mails=[mail_to_dict(m) for m in mails],
            code_count=sum(len(m.codes) for m in mails),
            summary=f"读取完成：返回 {len(mails)} 封邮件，识别 {sum(len(m.codes) for m in mails)} 个候选验证码。",
            refresh_token_rotated=bool(rotated_token),
            new_refresh_token=rotated_token,
        )
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400


@app.post("/api/batch-fetch")
def api_batch_fetch():
    try:
        payload = request.get_json(force=True) or {}
        accounts, parse_errors = parse_combo_lines(str(payload.get("combos") or ""), max_accounts=50)
        if not accounts and parse_errors:
            return jsonify(ok=False, error="没有可用账号行", parse_errors=parse_errors), 400
        if not accounts:
            return jsonify(ok=False, error="请粘贴账号或上传 TXT 文件"), 400
        limit = max(1, min(int(payload.get("limit") or 10), 100))
        keyword = str(payload.get("keyword") or "").strip()
        results = []
        total_mails = 0
        total_codes = 0
        for idx, account in enumerate(accounts, 1):
            try:
                mails, rotated_token = fetch_mail_items(account, limit=limit, keyword=keyword)
                mail_dicts = [mail_to_dict(m) for m in mails]
                code_count = sum(len(m.codes) for m in mails)
                total_mails += len(mails)
                total_codes += code_count
                results.append({
                    "ok": True,
                    "index": idx,
                    "email": account.email,
                    "mails": mail_dicts,
                    "mail_count": len(mails),
                    "code_count": code_count,
                    "refresh_token_rotated": bool(rotated_token),
                    "new_combo": f"{account.email}----{account.password}----{account.client_id}----{rotated_token}" if rotated_token else None,
                    "new_refresh_token": rotated_token,
                })
            except Exception as exc:
                results.append({"ok": False, "index": idx, "email": account.email, "error": str(exc)})
        success_count = sum(1 for r in results if r.get("ok"))
        return jsonify(
            ok=True,
            total=len(accounts),
            success=success_count,
            failed=len(accounts) - success_count,
            total_mails=total_mails,
            total_codes=total_codes,
            parse_errors=parse_errors,
            results=results,
            summary=f"批量完成：账号 {len(accounts)} 个，成功 {success_count} 个，邮件 {total_mails} 封，验证码候选 {total_codes} 个。",
        )
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 400


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8765"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
