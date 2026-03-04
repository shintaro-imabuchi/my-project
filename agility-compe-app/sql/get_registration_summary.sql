-- ============================================================
-- 申し込み状況サマリーを返す RPC 関数
-- Supabase の SQL Editor で実行してください
-- ============================================================
--
-- この関数は SECURITY DEFINER で動作するため、
-- anon キーのみで auth.users（全ユーザー数）にアクセスできます。
-- RLS ポリシーの変更は不要です。
--
-- ■ events カラムの型による使い分け ■
--   Supabase の GUI で "Array" として作成した場合は text[] 型です。
--   その場合は下記 SQL 内の unnest(events) をそのまま使用できます。
--
--   jsonb 型として作成した場合は unnest(events) の部分を
--   jsonb_array_elements_text(events) に変更してください。
-- ============================================================

CREATE OR REPLACE FUNCTION get_registration_summary()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_count  bigint;
    v_dog_count   bigint;
    v_event_counts jsonb;
BEGIN
    -- 参加登録者数（auth.users の全件数）
    SELECT COUNT(*) INTO v_user_count FROM auth.users;

    -- 登録済み犬数（dogs テーブルの全件数）
    SELECT COUNT(*) INTO v_dog_count FROM public.dogs;

    -- 種目別犬数
    -- events カラムが text[] 型の場合 ↓（デフォルト）
    SELECT jsonb_object_agg(event_name, cnt)
    INTO v_event_counts
    FROM (
        SELECT e AS event_name, COUNT(*) AS cnt
        FROM public.dogs, unnest(events) AS e
        GROUP BY e
    ) sub;

    -- events カラムが jsonb 型の場合は上記を下記に差し替えてください:
    -- SELECT jsonb_object_agg(event_name, cnt)
    -- INTO v_event_counts
    -- FROM (
    --     SELECT e AS event_name, COUNT(*) AS cnt
    --     FROM public.dogs, jsonb_array_elements_text(events) AS e
    --     GROUP BY e
    -- ) sub;

    RETURN json_build_object(
        'user_count',   v_user_count,
        'dog_count',    v_dog_count,
        'event_counts', COALESCE(v_event_counts, '{}'::jsonb)
    );
END;
$$;

-- 認証済みユーザーに実行権限を付与
GRANT EXECUTE ON FUNCTION get_registration_summary() TO authenticated;
