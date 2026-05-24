from __future__ import annotations

import argparse
import getpass
import json
import sys

from .core import fetch_mail_items, mail_to_dict, parse_combo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Outlook refresh_token 接码 CLI")
    parser.add_argument("combo", nargs="?", help="邮箱----密码----client_id----refresh_token；不传则隐藏输入")
    parser.add_argument("-n", "--limit", type=int, default=10, help="每个文件夹读取最近 N 封，默认 10")
    parser.add_argument("-k", "--keyword", default="", help="关键词过滤，可空")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    combo = args.combo or getpass.getpass("请输入 邮箱----密码----client_id----refresh_token: ")
    try:
        account = parse_combo(combo)
        mails, rotated = fetch_mail_items(account, limit=args.limit, keyword=args.keyword)
        if args.json:
            print(json.dumps({"ok": True, "mails": [mail_to_dict(m) for m in mails], "refresh_token_rotated": bool(rotated), "new_refresh_token": rotated}, ensure_ascii=False, indent=2))
        else:
            print(f"读取完成：{len(mails)} 封邮件")
            if rotated:
                print("提示：Microsoft 返回了新的 refresh_token，请更新你的原始资料。")
            for m in mails:
                codes = ", ".join(m.codes) if m.codes else "未识别到验证码"
                print(f"\n[{m.mailbox}] {m.date} {m.sender}\nSubject: {m.subject}\nCodes: {codes}\n{m.preview[:500]}")
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
