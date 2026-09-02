import json
import os
from datetime import date, timedelta

from supabase_client import get_supabase

EVENT_TYPES: list[str] = ["公式競技会", "練習会", "壮行会", "セミナー"]

# get_event_status()が返しうる全ラベル（表示・絞り込みの選択肢の並び順）。
# デフォルトでは「開催終了」だけ選択解除しておく（過去のイベントを見たい
# 場合は手動で選択できるようにする）。「開催中止」は見落とし防止のため
# デフォルトON。
STATUS_LABELS: list[str] = ["申込期間中", "申込期間前", "申込期間未定", "申込期間終了", "開催中止", "開催中", "開催終了"]
STATUS_DEFAULT_SELECTED: list[str] = [s for s in STATUS_LABELS if s != "開催終了"]

JKC_EXPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jkc_events_export.json")


def get_events(event_types: list[str] | None = None, published_only: bool = False) -> list[dict]:
    """開催情報一覧をSupabaseから取得する。

    Args:
        event_types: 絞り込むイベント種別。Noneなら全種別を取得する。
        published_only: Trueなら掲載ON（registration_open）のイベントのみ取得する。
            公開一覧ページ用。管理画面の一覧はFalse（全件）のまま使う。
    """
    query = get_supabase().table("events").select("*").order("event_date")
    if event_types:
        query = query.in_("event_type", event_types)
    if published_only:
        query = query.eq("registration_open", True)
    response = query.execute()
    return response.data


def insert_event(data: dict) -> None:
    """イベントをeventsテーブルに新規登録する。"""
    get_supabase().table("events").insert(data).execute()


def update_event(event_id: int, data: dict) -> None:
    """イベントをeventsテーブルで更新する。"""
    get_supabase().table("events").update(data).eq("id", event_id).execute()


def delete_event(event_id: int) -> None:
    """イベントをeventsテーブルから削除する。"""
    get_supabase().table("events").delete().eq("id", event_id).execute()


def load_jkc_export() -> list[dict] | None:
    """MulmoClaude（agility-eventsコレクション）が書き出したJKC取り込み用
    エクスポートファイルを読み込む。ファイルが存在しなければNoneを返す。
    """
    if not os.path.exists(JKC_EXPORT_PATH):
        return None
    with open(JKC_EXPORT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _normalize_name(name: str) -> str:
    """イベント名比較用に、半角/全角スペース等の表記ゆれを吸収する。"""
    return name.replace(" ", "").replace("　", "")


def _find_existing_match(record: dict, existing_by_source_id: dict, existing_list: list[dict]) -> dict | None:
    """1件のインポート候補に対応する既存eventsレコードを探す。

    1. source_idが一致すればそれを使う
    2. 一致しなければ、イベント名が同じ（空白の有無は無視）で、
       インポート候補のevent_dateが既存レコードの開催期間
       （event_date〜event_end_date）に含まれるものを探す
       （source_id導入前に手動登録された既存データや、複数日イベントの
       表現方法の違いを吸収するため）
    """
    source_id = record.get("source_id")
    if source_id and source_id in existing_by_source_id:
        return existing_by_source_id[source_id]

    r_date = record["event_date"]
    r_name = _normalize_name(record["name"])
    for e in existing_list:
        if _normalize_name(e["name"]) != r_name:
            continue
        e_start = e["event_date"]
        e_end = e.get("event_end_date") or e_start
        if e_start <= r_date <= e_end:
            return e
    return None


def preview_jkc_import(records: list[dict]) -> list[dict]:
    """取り込み対象レコードに、新規登録/更新/要確認の区別（_action）を付けて返す。

    - source_id一致、または名前＋開催期間の一致 → 「更新」
    - どちらにも一致しない → 「新規」
    - 複数のインポート候補が同じ既存レコードに一致してしまった場合は、
      片方だけ反映すると開催期間などの情報が失われる恐れがあるため、
      該当する全件を「要確認（重複）」とし、自動反映の対象から外す
      （例: コレクション側は複数日イベントを日ごとに別レコードで管理し、
      Supabase側は1レコードにまとめている、という表現の違いがある場合）
    """
    existing_list = (
        get_supabase()
        .table("events")
        .select("id, source_id, name, event_date, event_end_date")
        .execute()
        .data
    )
    existing_by_source_id = {e["source_id"]: e for e in existing_list if e.get("source_id")}

    result = []
    matched_existing_ids: dict[int, int] = {}
    for r in records:
        r = dict(r)
        matched = _find_existing_match(r, existing_by_source_id, existing_list)
        if matched:
            r["_action"] = "更新"
            r["_existing_id"] = matched["id"]
            matched_existing_ids[matched["id"]] = matched_existing_ids.get(matched["id"], 0) + 1
        else:
            r["_action"] = "新規"
            r["_existing_id"] = None
        result.append(r)

    # 同じ既存レコードに複数のインポート候補が一致した場合は「要確認（重複）」に変更
    for r in result:
        existing_id = r.get("_existing_id")
        if existing_id and matched_existing_ids.get(existing_id, 0) > 1:
            r["_action"] = "要確認（重複）"

    return result


def apply_jkc_import(records: list[dict]) -> int:
    """取り込み対象レコードをeventsテーブルへ反映する。

    「更新」は該当する既存レコード（id）をupdate、「新規」はinsertする。
    「要確認（重複）」は自動反映せずスキップする。
    掲載ON/OFF（registration_open）は常にTrueで取り込む。
    戻り値は反映した件数。
    """
    count = 0
    for r in records:
        if r.get("_action") == "要確認（重複）":
            continue
        data = {k: v for k, v in r.items() if not k.startswith("_") and v is not None}
        data["registration_open"] = True
        existing_id = r.get("_existing_id")
        if existing_id:
            get_supabase().table("events").update(data).eq("id", existing_id).execute()
        else:
            get_supabase().table("events").insert(data).execute()
        count += 1
    return count


def _to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def get_event_status(event: dict) -> tuple[str, str]:
    """イベントの状態を判定し、(表示種別, ラベル)を返す。

    表示種別は "success" / "info" / "caption" のいずれか（呼び出し側で
    st.success/st.info/st.captionの出し分けに使う）。

    判定の優先順位:
    1. イベントの開催期間（event_date〜event_end_date）が過去 → 「開催終了」
    2. イベントの開催期間に本日が含まれる → 「開催中」
    3. イベントの開催期間が未来の場合、申込期間から判定:
       - 申込開始日・締切日とも未登録 → 「申込期間未定」
       - 締切日が未登録の場合は、イベント開催日を仮の締切とみなす
         （申込開始日が未登録の場合は「既に申込期間に入っている」とみなす）
       - 開始日（登録があれば）が本日より先 → 「申込期間前」
       - 仮の締切を本日が過ぎている → 「申込期間終了」
       - それ以外 → 「申込期間中」

    掲載ON/OFF（registration_open）はここでは見ない。公開一覧に載せるか
    どうかだけを決める別の役割のため、get_events(published_only=True)側で
    絞り込む。

    開催中止（is_cancelled）は上記のどの判定よりも優先し、無条件で
    「開催中止」を返す（管理画面から手動でトグルする想定）。
    """
    if event.get("is_cancelled"):
        return "error", "開催中止"

    today = date.today()
    event_start = _to_date(event["event_date"])
    event_end = _to_date(event.get("event_end_date")) or event_start

    if event_end < today:
        return "caption", "開催終了"
    if event_start <= today <= event_end:
        return "success", "開催中"

    # ここに来る時点でイベントの開催期間は必ず未来（event_start > today）
    opens_on_raw = event.get("registration_opens_on")
    deadline_raw = event.get("registration_deadline")

    if not opens_on_raw and not deadline_raw:
        return "caption", "申込期間未定"

    opens_on = _to_date(opens_on_raw)
    effective_deadline = _to_date(deadline_raw) or event_start

    if opens_on and opens_on > today:
        return "info", "申込期間前"
    if today > effective_deadline:
        return "caption", "申込期間終了"
    return "success", "申込期間中"


# ============================================================
# 申込リマインド「Facebook投稿下書き」機能
#
# 個別ユーザーへのメール配信ではなく、管理者(今渕さん)がFacebook
# グループ/ページに手動でコピペ投稿する運用。そのため会員登録・認証は
# 不要で、「(イベント, マイルストーン)の組み合わせごとに、まだ下書きを
# 出していないものを一覧表示する」だけのシンプルな仕組みにしてある。
# ============================================================

_CONFIRMED_MILESTONES = [
    ("confirmed_3w", 21, "申込開始3週間以内"),
    ("confirmed_2w", 14, "申込開始2週間以内"),
    ("confirmed_1w", 7, "申込開始1週間以内"),
    ("confirmed_2d", 2, "申込開始2日以内"),
    ("confirmed_open", 0, "申込受付開始"),
]
_TENTATIVE_MILESTONES = [
    ("tentative_1_5m", 45, "開催1.5か月以内"),
    ("tentative_1m", 30, "開催1か月以内"),
]


def _event_milestones(event: dict) -> list[tuple[str, date, str]]:
    """イベントに適用すべき (milestone_key, 目標日, ラベル) のリストを返す。

    申込開始日(registration_opens_on)が登録済みのイベントは開始日起点、
    未登録（申込期間未定）のイベントは開催日起点のマイルストーンを使う。
    get_event_status()の「申込期間未定」判定とは異なり、締切日の有無は
    見ない（開始日が無ければ常に未定パターン扱い）。

    確定パターンの最後の項目(confirmed_open、目標日=開始日そのもの)は
    「ただいま申込受付中です」の告知用。開始日を過ぎてもこれが候補に残る
    ことで、get_due_facebook_drafts()側の「最も本日に近いものを採用する」
    ロジックにより、開始前カウントダウンの代わりに受付中の告知が選ばれる。
    ただし締切(なければ開催日)を過ぎたら、これ以上の告知は無意味なので
    候補自体を返さない(空リスト)。この状態は公開一覧側の「申込期間終了」
    表示で十分に伝わる。
    """
    opens_on = _to_date(event.get("registration_opens_on"))
    event_date = _to_date(event["event_date"])
    if opens_on:
        effective_deadline = _to_date(event.get("registration_deadline")) or event_date
        if date.today() > effective_deadline:
            return []
        return [
            (key, opens_on - timedelta(days=days), label)
            for key, days, label in _CONFIRMED_MILESTONES
        ]
    return [
        (key, event_date - timedelta(days=days), label)
        for key, days, label in _TENTATIVE_MILESTONES
    ]


def build_draft_text(event: dict, milestone_key: str, label: str) -> str:
    """Facebook投稿用の下書き文面を組み立てる。"""
    date_range = event["event_date"]
    end = event.get("event_end_date")
    if end and end != event["event_date"]:
        date_range += f"〜{end}"

    lines = [f"📢 {event['name']}", f"開催日: {date_range}"]
    if event.get("venue"):
        lines.append(f"会場: {event['venue']}")
    if event.get("organizer_name"):
        lines.append(f"主催: {event['organizer_name']}")

    if milestone_key == "confirmed_open":
        deadline = event.get("registration_deadline")
        lines.append(
            f"🎉 ただいま申込受付中です！　申込開始日: {event.get('registration_opens_on')}"
            + (f"　締切: {deadline}" if deadline else "")
        )
    elif milestone_key.startswith("confirmed_"):
        lines.append(f"⏰ {label}です！　申込開始日: {event.get('registration_opens_on')}")
    else:
        lines.append(f"📅 {label}になりました。申込期間はまだ未公開です。")

    guideline_url = event.get("guideline_url")
    if guideline_url:
        lines.append(f"詳細: {guideline_url}")
    return "\n".join(lines)


def get_due_facebook_drafts() -> list[dict]:
    """本日時点の状況スナップショットとして表示すべきFacebook下書きの一覧を返す。

    公開一覧に載っている(掲載ON)全種別のイベントが対象。開催中止・開催日を
    過ぎたイベントは対象外。

    「一度出したら二度と出さない」通知ではなく、「今その時点で該当する
    イベントの状況を毎回まとめて表示する」ためのもの。そのため投稿済み
    管理は行わない — 管理者が任意のタイミングで何度でも見返し、その都度
    Facebookに投稿してよい(前回投稿した内容と重複しても構わない)。

    1イベントにつき候補は最大1件: 複数のマイルストーンが同時に「本日以前」
    になっていても、そのうち最も本日に近い(=一番遅い目標日の)ものだけを
    採用する(例: 3週間前を見逃していても、2週間前の方が新しければそちらを
    表示する)。

    戻り値は開催日の近い順(1つの投稿にまとめて読んだときに自然な並びに
    なるよう)。各要素:
    {"event": dict, "milestone_key": str, "target_date": date, "label": str,
     "draft_text": str}
    """
    today = date.today()
    events = get_events(published_only=True)

    due = []
    for event in events:
        if event.get("is_cancelled"):
            continue
        event_date = _to_date(event["event_date"])
        if event_date < today:
            continue
        due_so_far = [m for m in _event_milestones(event) if m[1] <= today]
        if not due_so_far:
            continue
        milestone_key, target_date, label = max(due_so_far, key=lambda m: m[1])
        due.append(
            {
                "event": event,
                "milestone_key": milestone_key,
                "target_date": target_date,
                "label": label,
                "draft_text": build_draft_text(event, milestone_key, label),
            }
        )
    due.sort(key=lambda d: d["event"]["event_date"])
    return due


_EVENTS_SITE_URL = "https://dog-agility-events.streamlit.app/"


def _draft_header() -> str:
    today = date.today()
    return (
        "申込を忘れてしまわないように。#アジリティー #agility\n"
        f"{today.month}月{today.day}日現在の申込期間状況。\n"
        f"詳細は {_EVENTS_SITE_URL}"
    )


def build_combined_draft_text(drafts: list[dict]) -> str:
    """複数イベント分の下書きを、冒頭の定型文に続けて渡された順序のまま
    区切り線でつなぎ、1つのFacebook投稿用テキストにまとめる。"""
    body = "\n\n――――――――――\n\n".join(d["draft_text"] for d in drafts)
    return f"{_draft_header()}\n\n{body}"
