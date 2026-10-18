from datetime import date, timedelta

from supabase_client import get_supabase

EVENT_TYPES: list[str] = ["公式競技会", "練習会", "壮行会", "セミナー"]

# get_event_status()が返しうる全ラベル（表示・絞り込みの選択肢の並び順）。
# デフォルトは申込期間に関する4状態（中・前・未定・終了）のみ選択。
# 「開催中止」「開催中」「開催終了」は既に結果が確定しているイベントのため、
# 見たい場合に手動で選択する運用とする。
STATUS_LABELS: list[str] = ["申込期間中", "申込期間前", "申込期間未定", "申込期間終了", "開催中止", "開催中", "開催終了"]
STATUS_DEFAULT_SELECTED: list[str] = ["申込期間中", "申込期間前", "申込期間未定", "申込期間終了"]


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

    未定パターン(申込開始日が未登録)には「受付中」に相当する最終告知が
    無いため、確定パターンと同様に開催日を過ぎたら(=開催当日も含む)
    空リストを返す。これが無いと、申込期間が最後まで公開されなかった
    イベントが、開催当日・開催後もずっと「開催1か月以内になりました」の
    ような古い告知のまま表示され続けてしまう。
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
    if date.today() >= event_date:
        return []
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

    if milestone_key == "confirmed_open":
        deadline = event.get("registration_deadline")
        lines.append(
            f"🎉 ただいま申込受付中です！　申込開始日: {event.get('registration_opens_on')}"
            + (f"　締切: {deadline}" if deadline else "")
        )
    elif milestone_key.startswith("confirmed_"):
        deadline = event.get("registration_deadline")
        lines.append(
            f"⏰ {label}です！　申込開始日: {event.get('registration_opens_on')}"
            + (f"　締切: {deadline}" if deadline else "")
        )
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


_EVENTS_SITE_URL = "https://agility-events.puffin.tokyo.jp/"


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
