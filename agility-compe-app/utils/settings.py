from supabase_client import get_supabase


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
