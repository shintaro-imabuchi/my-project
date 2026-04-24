"""参加登録アプリのスリープ回避スクリプト。

Supabase Auth REST API でログイン→ログアウトを行いスリープを防ぐ。
必要な環境変数:
  APP_ENTRY_URL   : 参加登録アプリのURL
  SUPABASE_URL    : SupabaseプロジェクトURL
  SUPABASE_KEY    : Supabase anon key
  ENTRY_EMAIL     : ログインに使うメールアドレス
  ENTRY_PASSWORD  : ログインに使うパスワード
"""

import os
import sys

import httpx

APP_ENTRY_URL: str = os.environ["APP_ENTRY_URL"]
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]
ENTRY_EMAIL: str = os.environ["ENTRY_EMAIL"]
ENTRY_PASSWORD: str = os.environ["ENTRY_PASSWORD"]

TIMEOUT = 30.0
AUTH_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Content-Type": "application/json",
}


def login() -> str:
    """Supabase Authにログインしてアクセストークンを返す。"""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers=AUTH_HEADERS,
        json={"email": ENTRY_EMAIL, "password": ENTRY_PASSWORD},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    token: str = resp.json()["access_token"]
    print(f"ログイン成功: {ENTRY_EMAIL}")
    return token


def logout(token: str) -> None:
    """Supabase Authからログアウトする。"""
    resp = httpx.post(
        f"{SUPABASE_URL}/auth/v1/logout",
        headers={**AUTH_HEADERS, "Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    print("ログアウト成功")


def ping_app() -> None:
    """StreamlitアプリURLにアクセスしてスリープを防ぐ。"""
    resp = httpx.get(APP_ENTRY_URL, timeout=TIMEOUT, follow_redirects=True)
    print(f"アプリアクセス完了: HTTP {resp.status_code}")


def main() -> None:
    """ログイン→ログアウト→アプリアクセスを実行する。"""
    try:
        ping_app()
        token = login()
        logout(token)
    except httpx.HTTPStatusError as e:
        print(f"HTTPエラー: {e.response.status_code} {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"接続エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
