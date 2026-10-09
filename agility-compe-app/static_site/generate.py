"""開催情報一覧（agility-events.puffin.tokyo.jp）の静的サイトを生成するビルドスクリプト。

Streamlitに依存しない独立スクリプト。`python static_site/generate.py`で実行し、
dist/にindex.html・robots.txt・static一式を書き出す。Supabase接続情報は
環境変数（SUPABASE_URL / SUPABASE_KEY）から読む（st.secretsは使わない）。

app_events_public.pyの表示ロジックを踏襲しているが、当スクリプトはHTMLを
組み立てるだけでStreamlitのUI操作（フィルタの選択状態など）は行わない。
フィルタはビルド後のHTMLに埋め込んだdata属性をstatic/filter.jsが
クライアントサイドで切り替える。
"""

import os
import shutil
import sys
from datetime import date

from jinja2 import Environment, FileSystemLoader
from supabase import Client, create_client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.events import (  # noqa: E402
    EVENT_TYPES,
    get_event_status,
)

_THIS_DIR = os.path.dirname(__file__)
_DIST_DIR = os.path.join(_THIS_DIR, "dist")
_SITE_URL = "https://agility-events.puffin.tokyo.jp/"

_BADGE_COLORS: dict[str, str] = {
    "公式競技会": "red",
    "練習会": "blue",
    "壮行会": "orange",
    "セミナー": "green",
}

_STATUS_KIND_CLASS: dict[str, str] = {
    "success": "status-success",
    "info": "status-info",
    "error": "status-error",
    "caption": "status-caption",
}

_JKC_SOURCE_NOTICE = (
    "公式競技会の情報は、JKCイベントスケジュールをもとに転載しています。"
    "新規イベントの追加や既存イベントの変更反映（日程・会場・申込期間など）"
    "が遅れる場合があることをご了解ください。"
)

# このサイト（一般公開・SEO流入を想定）は、想定ユーザーにシンプルに使ってもらうため、
# utils.events.STATUS_LABELS（内部向けpages/03_events.pyが使う全7状態）より絞った
# 3状態だけをフィルタ選択肢として出す。2026-10-09のユーザー方針により決定。
_PUBLIC_STATUS_LABELS = ["申込期間中", "申込期間前", "申込期間未定"]
_PUBLIC_DEFAULT_STATUS_LABELS = ["申込期間中", "申込期間前"]

# 上記以外の状態（受付終了・結果が確定済みのイベント）は、一覧に出す意味が薄いため
# 生成データ自体から除外する（MulmoClaude側のagility-eventsコレクションや
# Supabaseの行自体は消さず、このサイトの表示対象からだけ除外する）。
_EXCLUDED_STATUS_LABELS = {"申込期間終了", "開催中止", "開催中", "開催終了"}


def get_supabase() -> Client:
    """環境変数からSupabaseクライアントを作成する（st.secretsは使わない）。"""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def get_published_events() -> list[dict]:
    """掲載ON（registration_open）のイベント一覧を開催日順に取得する。

    種別の絞り込みはここでは行わない。クライアントサイドJSが全件から
    絞り込むため、生成時点では全種別を取得する。
    """
    return (
        get_supabase()
        .table("events")
        .select("*")
        .eq("registration_open", True)
        .order("event_date")
        .execute()
        .data
    )


def _format_date(iso_str: str) -> str:
    """ISO形式の日付文字列を表示用文字列にする。"""
    d = date.fromisoformat(iso_str)
    return f"{d.year}/{d.month}/{d.day}"


def _format_date_range(event: dict) -> str:
    """開催日〜終了日を表示用文字列にする。"""
    text = _format_date(event["event_date"])
    end_raw = event.get("event_end_date")
    if end_raw and end_raw != event["event_date"]:
        text += f" 〜 {_format_date(end_raw)}"
    return text


def _format_registration_period(event: dict) -> str | None:
    """申込開始日〜締切日を表示用文字列にする。どちらも未設定ならNoneを返す。"""
    opens_on = event.get("registration_opens_on")
    deadline = event.get("registration_deadline")
    if opens_on and deadline:
        return f"{_format_date(opens_on)} 〜 {_format_date(deadline)}"
    if opens_on:
        return f"{_format_date(opens_on)} 〜"
    if deadline:
        return f"〜 {_format_date(deadline)}"
    return None


def _sort_by_proximity(events: list[dict]) -> list[dict]:
    """開催日が近い順（当日以降を優先）に並び替える。過去分は新しい順で後ろに続ける。"""
    today = date.today()
    upcoming = [e for e in events if date.fromisoformat(e["event_date"]) >= today]
    past = [e for e in events if date.fromisoformat(e["event_date"]) < today]
    past.reverse()
    return upcoming + past


def build_card(event: dict) -> dict:
    """1件のイベントを、テンプレートに渡す表示用データに変換する。"""
    status_kind, status_label = get_event_status(event)
    guideline_url = event.get("guideline_url")
    registration_url = event.get("registration_url")
    return {
        "name": event["name"],
        "is_cancelled": bool(event.get("is_cancelled")),
        "event_type": event["event_type"],
        "badge_color": _BADGE_COLORS.get(event["event_type"], "gray"),
        "date_range": _format_date_range(event),
        "venue": event.get("venue"),
        "registration_period": _format_registration_period(event),
        "status_label": status_label,
        "status_class": _STATUS_KIND_CLASS.get(status_kind, "status-caption"),
        "guideline_url": guideline_url,
        "registration_url": registration_url,
        "no_url": not guideline_url and not registration_url,
        "registration_note": event.get("registration_note"),
        "notes": event.get("notes"),
    }


def render_site(cards: list[dict]) -> str:
    """テンプレートをレンダリングし、生成したHTML文字列を返す。"""
    env = Environment(
        loader=FileSystemLoader(os.path.join(_THIS_DIR, "templates")),
        autoescape=True,
    )
    template = env.get_template("index.html.jinja")
    return template.render(
        cards=cards,
        today=_format_date(date.today().isoformat()),
        jkc_source_notice=_JKC_SOURCE_NOTICE,
        event_types=EVENT_TYPES,
        status_labels=_PUBLIC_STATUS_LABELS,
        default_event_types=["公式競技会"],
        default_status_labels=_PUBLIC_DEFAULT_STATUS_LABELS,
        site_url=_SITE_URL,
    )


def main() -> None:
    """開催情報一覧の静的サイトをdist/に生成する。"""
    events = get_published_events()
    cards = [build_card(e) for e in _sort_by_proximity(events)]
    cards = [c for c in cards if c["status_label"] not in _EXCLUDED_STATUS_LABELS]

    os.makedirs(_DIST_DIR, exist_ok=True)
    html = render_site(cards)
    with open(os.path.join(_DIST_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    with open(os.path.join(_DIST_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n")

    dist_static_dir = os.path.join(_DIST_DIR, "static")
    os.makedirs(dist_static_dir, exist_ok=True)
    for filename in ("style.css", "filter.js"):
        shutil.copyfile(
            os.path.join(_THIS_DIR, "static", filename),
            os.path.join(dist_static_dir, filename),
        )

    print(f"{len(cards)}件のイベントを出力しました")


if __name__ == "__main__":
    main()
