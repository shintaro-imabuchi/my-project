from datetime import date

from supabase_client import get_supabase

EVENT_TYPES: list[str] = ["公式競技会", "練習会", "壮行会", "セミナー"]


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
         （申込開始日が未登録の場合は「既に受付開始済み」とみなす）
       - 開始日（登録があれば）が本日より先 → 「申込受付前」
       - 仮の締切を本日が過ぎている → 「申込受付終了」
       - それ以外 → 「申込受付中」

    掲載ON/OFF（registration_open）はここでは見ない。公開一覧に載せるか
    どうかだけを決める別の役割のため、get_events(published_only=True)側で
    絞り込む。
    """
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
        return "info", "申込受付前"
    if today > effective_deadline:
        return "caption", "申込受付終了"
    return "success", "申込受付中"
