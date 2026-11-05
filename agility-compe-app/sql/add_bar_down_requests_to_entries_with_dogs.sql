-- ============================================================
-- get_entries_with_dogs に bar_down_requests を追加
-- 2026-11-05
--
-- 背景: 出走表（app_staff.py）の出走順を「種目・クラス内でバーの高さ昇順」
-- に変更するには、各エントリーのバーダウン希望（entries.bar_down_requests）
-- が必要。既存のRPC関数は events しか返していなかったため、列を追加する。
--
-- 戻り値にフィールドを追加するだけなので、既存の呼び出し元（app_admin.py等、
-- eventsしか参照していない）には影響しない。
--
-- 注意: PostgreSQLはRETURNS TABLEの列構成が変わる場合CREATE OR REPLACEだけでは
-- 更新できない（42P13エラー）ため、先にDROP FUNCTIONが必要。
-- ============================================================

DROP FUNCTION IF EXISTS get_entries_with_dogs(bigint);

CREATE OR REPLACE FUNCTION get_entries_with_dogs(p_competition_id bigint)
RETURNS TABLE (
    entry_id           bigint,
    dog_id              uuid,
    user_id            uuid,
    user_name          text,
    dog_name           text,
    breed              text,
    dog_class          text,
    events             text[],
    bar_down_requests  jsonb
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        e.id AS entry_id,
        d.id AS dog_id,
        d.user_id,
        (u.raw_user_meta_data->>'name')::text AS user_name,
        d.dog_name,
        d.breed,
        d.dog_class,
        e.events,
        e.bar_down_requests
    FROM entries e
    JOIN dogs d ON d.id = e.dog_id
    JOIN auth.users u ON u.id = d.user_id
    WHERE e.competition_id = p_competition_id
    ORDER BY user_name, d.created_at;
$$;

GRANT EXECUTE ON FUNCTION get_entries_with_dogs(bigint) TO authenticated, anon;
