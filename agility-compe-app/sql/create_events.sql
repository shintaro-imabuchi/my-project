-- ============================================================
-- events: 「開催情報一覧」機能（一般公開・ログイン不要）のためのテーブル
-- 2026-08-23
--
-- competitionsとは別テーブル。competitionsは「実際にこのapp上で
-- 参加登録・出走表・成績を運用する大会」を表すのに対し、eventsは
-- 「JKC公式競技会・練習会・壮行会・セミナーなど、告知だけ先に
-- 一覧で見せたいイベント全般」を表す。運用が始まったら
-- competition_idで両者を紐付けられるようにしてある（任意・将来用）。
-- ============================================================

CREATE TABLE IF NOT EXISTS events (
    id                      bigserial   PRIMARY KEY,
    name                    text        NOT NULL,
    event_type              text        NOT NULL DEFAULT '練習会',
        -- '公式競技会' / '練習会' / '壮行会' / 'セミナー'（competitionsと同じ語彙）
    organizer_name          text,                                   -- クラブ名（表示用）
    venue                   text,
    event_date              date        NOT NULL,
    event_end_date          date,
    registration_opens_on   date,
    registration_deadline   date,
    registration_open       boolean     NOT NULL DEFAULT true,
    registration_url        text,       -- 参加登録サイトのURL（この機能の核心）
    registration_note       text,       -- URL以外の申込方法の補足（任意）
    competition_id          bigint      REFERENCES competitions(id) ON DELETE SET NULL,
        -- このapp上で実際に運用が始まったcompetitionsと紐付ける（将来用・任意）
    notes                   text,
    created_at              timestamptz DEFAULT now(),
    updated_at              timestamptz DEFAULT now()
);

CREATE OR REPLACE FUNCTION update_events_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_events_updated_at ON events;
CREATE TRIGGER trg_events_updated_at
BEFORE UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION update_events_updated_at();

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- 閲覧は誰でも可（公開一覧ページ用）
DROP POLICY IF EXISTS "events_select" ON events;
CREATE POLICY "events_select" ON events
    FOR SELECT USING (true);

-- 書き込みはサインイン済みユーザーのみ（管理者画面はsign_in_as_owner()で
-- 既にauthenticatedになっている前提。competitionsのようなowner_user_id列は
-- 持たせない — このeventsは特定の大会の所有者ではなく、このデプロイの
-- 管理者が横断的に管理する一覧のため）
--
-- 【将来のマルチテナント化に向けた既知の制約】
-- 現状は「1デプロイ=1管理者アカウント」なので問題にならないが、複数クラブが
-- それぞれ別ownerアカウントを持つ本格的なマルチテナント運用になった場合、
-- このポリシーのままだと「どのクラブのownerでサインインしても他クラブの
-- eventsまで編集・削除できてしまう」。その段階になったら、events側にも
-- 何らかの所有者列（例: created_by）を追加してRLSを絞り込むこと。
DROP POLICY IF EXISTS "events_write" ON events;
CREATE POLICY "events_write" ON events
    FOR ALL TO authenticated USING (true) WITH CHECK (true);
