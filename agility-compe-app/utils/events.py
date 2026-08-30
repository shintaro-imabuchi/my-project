from datetime import date

from supabase_client import get_supabase

EVENT_TYPES: list[str] = ["公式競技会", "練習会", "壮行会", "セミナー"]


def get_events(event_types: list[str] | None = None) -> list[dict]:
    """開催情報一覧をSupabaseから取得する。

    Args:
        event_types: 絞り込むイベント種別。Noneなら全種別を取得する。
    """
    query = get_supabase().table("events").select("*").order("event_date")
    if event_types:
        query = query.in_("event_type", event_types)
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


def is_registration_open(event: dict) -> bool:
    """イベントが申込受付中かどうかを判定する。

    registration_openが真、かつregistration_deadlineが未設定または
    当日以降であれば受付中とみなす。
    """
    if not event.get("registration_open"):
        return False
    deadline = event.get("registration_deadline")
    if not deadline:
        return True
    return date.fromisoformat(deadline) >= date.today()
