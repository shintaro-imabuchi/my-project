-- ============================================================
-- posted_milestones: 「申込リマインドFacebook投稿下書き」機能の
-- 投稿済み管理テーブル。
--
-- 個別ユーザー宛のメール配信ではなく、管理者(今渕さん)がFacebook
-- グループ/ページへ手動投稿する運用のため、宛先(user_id)は持たない。
-- (event_id, milestone_key) の組み合わせをキーに「もう下書きを出し
-- 終えた／投稿した」ことだけを記録し、管理画面の「Facebook投稿下書き」
-- 一覧から同じ組み合わせを除外する。
--
-- milestone_key の値:
--   confirmed_3w / confirmed_2w / confirmed_1w / confirmed_2d
--     … 申込期間確定イベント。registration_opens_on の 3週間/2週間/
--       1週間/2日前
--   tentative_1_5m / tentative_1m
--     … 申込期間未定イベント。event_date の 1.5か月/1か月前
-- ============================================================

CREATE TABLE IF NOT EXISTS posted_milestones (
    id            bigserial   PRIMARY KEY,
    event_id      bigint      NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    milestone_key text        NOT NULL,
    posted_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, milestone_key)
);

ALTER TABLE posted_milestones ENABLE ROW LEVEL SECURITY;

-- 公開一覧側では一切参照しない管理者専用テーブルのため、
-- authenticated（sign_in_as_owner()済みの管理画面）にのみ全操作を許可する。
DROP POLICY IF EXISTS "posted_milestones_all" ON posted_milestones;
CREATE POLICY "posted_milestones_all" ON posted_milestones
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
