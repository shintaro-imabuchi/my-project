from supabase_client import get_supabase

_DEFAULT_EVENT_FEES: dict[str, int] = {
    "ビギナー": 2000,
    "JP1.5": 3000,
    "JP2.5": 3000,
    "AG1": 3000,
    "AG2": 3000,
    "AG3": 3000,
}


def get_registration_open() -> bool:
    """新規登録受付中かどうかをSupabaseから取得する。

    取得に失敗した場合はTrueを返し、受付中として扱う。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "registration_open")
            .single()
            .execute()
        )
        return bool(response.data["value"])
    except Exception:
        return True


def set_registration_open(value: bool) -> None:
    """新規登録受付状態をSupabaseに保存する。

    Args:
        value: Trueなら受付中、Falseなら締め切り。
    """
    get_supabase().table("settings").update(
        {"value": value}
    ).eq("key", "registration_open").execute()


def get_event_fees() -> dict[str, int]:
    """競技種目と参加料金の対応辞書をSupabaseから取得する。

    settingsテーブルの key='event_fees' 行から読み込む。
    行が存在しない場合やエラー時はデフォルト値を返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "event_fees")
            .single()
            .execute()
        )
        data = response.data.get("value")
        if isinstance(data, list):
            return {
                item["name"]: int(item["fee"])
                for item in data
                if item.get("name")
            }
        return _DEFAULT_EVENT_FEES
    except Exception:
        return _DEFAULT_EVENT_FEES


def set_event_fees(event_fees: dict[str, int]) -> None:
    """競技種目と参加料金の対応辞書をSupabaseに保存する。

    settingsテーブルへ key='event_fees' でupsertする。
    種目の順序は配列の順番で保持される。

    Args:
        event_fees: 種目名をキー、料金（円）を値とする辞書。
    """
    data = [{"name": name, "fee": fee} for name, fee in event_fees.items()]
    get_supabase().table("settings").upsert(
        {"key": "event_fees", "value": data},
        on_conflict="key",
    ).execute()


def get_login_message() -> str | None:
    """ログイン画面に表示するメッセージをSupabaseから取得する。

    行が存在しない場合、値がNullの場合、エラー時はNoneを返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "login_message")
            .single()
            .execute()
        )
        val = response.data.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        return None


def set_login_message(message: str | None) -> None:
    """ログイン画面に表示するメッセージをSupabaseに保存する。

    Args:
        message: 表示するメッセージ。Noneまたは空文字列の場合はNullを保存する。
    """
    value = message.strip() if message and message.strip() else None
    get_supabase().table("settings").upsert(
        {"key": "login_message", "value": value},
        on_conflict="key",
    ).execute()


def get_guideline_url() -> str | None:
    """トップ画面「練習会要綱を見る」のURLをSupabaseから取得する。

    行が存在しない場合、値がNullの場合、エラー時はNoneを返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "guideline_url")
            .single()
            .execute()
        )
        val = response.data.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        return None


def set_guideline_url(url: str | None) -> None:
    """トップ画面「練習会要綱を見る」のURLをSupabaseに保存する。

    Args:
        url: URL文字列。Noneまたは空文字列の場合はNullを保存する。
    """
    value = url.strip() if url and url.strip() else None
    get_supabase().table("settings").upsert(
        {"key": "guideline_url", "value": value},
        on_conflict="key",
    ).execute()


def get_notice_url() -> str | None:
    """ホーム画面「練習会実施のご案内を見る」のURLをSupabaseから取得する。

    行が存在しない場合、値がNullの場合、エラー時はNoneを返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "notice_url")
            .single()
            .execute()
        )
        val = response.data.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        return None


def set_notice_url(url: str | None) -> None:
    """ホーム画面「練習会実施のご案内を見る」のURLをSupabaseに保存する。

    Args:
        url: URL文字列。Noneまたは空文字列の場合はNullを保存する。
    """
    value = url.strip() if url and url.strip() else None
    get_supabase().table("settings").upsert(
        {"key": "notice_url", "value": value},
        on_conflict="key",
    ).execute()


def get_top_image_url() -> str | None:
    """トップ画面に表示する画像のURLをSupabaseから取得する。

    行が存在しない場合、値がNullの場合、エラー時はNoneを返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "top_image_url")
            .single()
            .execute()
        )
        val = response.data.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        return None


def set_top_image_url(url: str | None) -> None:
    """トップ画面に表示する画像のURLをSupabaseに保存する。

    Args:
        url: URL文字列。Noneまたは空文字列の場合はNullを保存する。
    """
    value = url.strip() if url and url.strip() else None
    get_supabase().table("settings").upsert(
        {"key": "top_image_url", "value": value},
        on_conflict="key",
    ).execute()


def get_home_info_message() -> str | None:
    """ログイン後ホーム画面に表示するお知らせをSupabaseから取得する。

    行が存在しない場合、値がNullの場合、エラー時はNoneを返す。
    """
    try:
        response = (
            get_supabase()
            .table("settings")
            .select("value")
            .eq("key", "home_info_message")
            .single()
            .execute()
        )
        val = response.data.get("value")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return None
    except Exception:
        return None


def set_home_info_message(message: str | None) -> None:
    """ログイン後ホーム画面に表示するお知らせをSupabaseに保存する。

    Args:
        message: 表示するメッセージ。Noneまたは空文字列の場合はNullを保存する。
    """
    value = message.strip() if message and message.strip() else None
    get_supabase().table("settings").upsert(
        {"key": "home_info_message", "value": value},
        on_conflict="key",
    ).execute()
