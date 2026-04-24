"""Streamlit管理者アプリへの自動ログインスクリプト。

GitHub Actions から実行され、アプリをスリープさせないために使用する。
環境変数 APP_URL と ADMIN_PASSWORD が必要。
"""

import os
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

APP_URL: str = os.environ["APP_URL"]
ADMIN_PASSWORD: str = os.environ["ADMIN_PASSWORD"]

# Streamlitアプリの起動待ち・操作のタイムアウト(ms)
PAGE_TIMEOUT = 60_000
ACTION_TIMEOUT = 30_000


def main() -> None:
    """アプリにアクセスしてログインを実行する。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)

        try:
            print(f"アクセス中: {APP_URL}")
            page.goto(APP_URL, timeout=PAGE_TIMEOUT)

            # Streamlitアプリの読み込み完了を待つ
            page.wait_for_selector("input[type='password']", timeout=PAGE_TIMEOUT)
            print("ログインフォームを検出しました")

            # パスワード入力
            page.fill("input[type='password']", ADMIN_PASSWORD)

            # ログインボタンをクリック（「ログイン」というテキストのボタン）
            page.get_by_role("button", name="ログイン").click()

            # ログイン成功の確認（管理者メニューが表示されるまで待つ）
            page.wait_for_selector("text=管理者メニュー", timeout=PAGE_TIMEOUT)
            print("ログイン成功")

        except PlaywrightTimeoutError as e:
            print(f"タイムアウトエラー: {e}", file=sys.stderr)
            page.screenshot(path="error_screenshot.png")
            print("エラー時のスクリーンショットを error_screenshot.png に保存しました")
            sys.exit(1)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
