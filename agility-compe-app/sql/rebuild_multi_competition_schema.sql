-- ============================================================
-- マルチ大会・マルチ主催者対応スキーマへの作り直し
-- 2026-08-14
--
-- 前提: 既存データ（テスト用のみ、実利用者なし）は保持不要。
-- 既存テーブルを DROP して作り直す。
-- 実行順序を守ること（依存関係があるため）。
-- ============================================================

-- --- 既存オブジェクトを削除 -----------------------------------
DROP FUNCTION IF EXISTS get_race_results(bigint);
DROP FUNCTION IF EXISTS get_registration_summary();
DROP FUNCTION IF EXISTS get_participants_with_dogs();
DROP TABLE IF EXISTS race_results;
DROP TABLE IF EXISTS race_configs;
DROP TABLE IF EXISTS entries;
DROP TABLE IF EXISTS settings;
-- dogs は列を削除するだけで再利用する（下記参照）


-- ============================================================
-- 1. competitions: 大会・練習会マスター
--    Phase 1（開催情報の公開）と Phase 2（大会運営）の共通の土台。
--    旧 settings（registration_open, event_fees）をここに統合。
-- ============================================================
CREATE TABLE competitions (
    id                      bigserial   PRIMARY KEY,
    name                    text        NOT NULL,
    event_type              text        NOT NULL DEFAULT '練習会',
        -- '公式競技会' / '練習会' / '壮行会' / 'セミナー'
    organizer_name          text,                                    -- クラブ名（表示用）
    owner_user_id           uuid        NOT NULL REFERENCES auth.users(id),
        -- この大会の管理権限を持つユーザー（クラブ運営者アカウント）
    venue                   text,
    event_date              date        NOT NULL,
    event_end_date          date,
    registration_opens_on   date,
    registration_deadline   date,
    registration_open       boolean     NOT NULL DEFAULT true,       -- 旧 settings.registration_open
    event_fees              jsonb,
        -- 旧 settings.event_fees。例:
        -- [{"name":"ビギナー","fee":2000}, {"name":"JP1.5","fee":3000}, ...]
    guideline_url           text,       -- 旧 settings.guideline_url（トップ画面「練習会要綱を見る」）
    top_image_url           text,       -- 旧 settings.top_image_url（トップ画面表示画像）
    notice_url              text,       -- 旧 settings.notice_url（ホーム画面「練習会実施のご案内を見る」）
    home_info_message       text,       -- 旧 settings.home_info_message（ホーム画面お知らせ）
    notes                   text,
    created_at              timestamptz DEFAULT now(),
    updated_at              timestamptz DEFAULT now()
);

CREATE OR REPLACE FUNCTION update_competitions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_competitions_updated_at
BEFORE UPDATE ON competitions
FOR EACH ROW EXECUTE FUNCTION update_competitions_updated_at();

ALTER TABLE competitions ENABLE ROW LEVEL SECURITY;

-- 閲覧は誰でも可（Phase1の公開カレンダーとして使うため）
CREATE POLICY "competitions_select" ON competitions
    FOR SELECT USING (true);

-- 追加・変更・削除は、その大会の owner_user_id 本人のみ
CREATE POLICY "competitions_insert" ON competitions
    FOR INSERT TO authenticated WITH CHECK (owner_user_id = auth.uid());

CREATE POLICY "competitions_update" ON competitions
    FOR UPDATE TO authenticated USING (owner_user_id = auth.uid()) WITH CHECK (owner_user_id = auth.uid());

CREATE POLICY "competitions_delete" ON competitions
    FOR DELETE TO authenticated USING (owner_user_id = auth.uid());


-- ============================================================
-- 1b. app_settings: サイト全体で共通の設定（大会に紐付かないもの）
--     旧 settings.login_message（ログイン前トップ画面の告知文）のみ移設。
--     他の項目（guideline_url等）は大会ごとの情報として competitions へ移設済み。
--     現状の管理画面はSupabase Authでのログインを行わず、共有パスワードで
--     ガードした上でanonキーのまま読み書きしているため、旧 settings テーブル
--     と同じく anon/authenticated に書き込みを許可する（アプリ側のパスワード
--     画面が唯一のガード）。
-- ============================================================
CREATE TABLE app_settings (
    key         text        PRIMARY KEY,
    value       text,
    updated_at  timestamptz DEFAULT now()
);

ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "app_settings_select" ON app_settings
    FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "app_settings_write" ON app_settings
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);


-- ============================================================
-- 2. dogs: 犬プロフィール（大会をまたいで使い回す）
--    events 列は entries テーブルへ移設したため削除。
-- ============================================================
ALTER TABLE dogs DROP COLUMN IF EXISTS events;
-- 残る列: id, user_id, dog_name, breed, dog_class, created_at 等


-- ============================================================
-- 3. entries: 大会ごとの参加登録
--    「どの犬が、どの大会に、どの種目でエントリーしたか」
--    旧 dogs.events（大会と紐付いていなかった）の移設先。
-- ============================================================
CREATE TABLE entries (
    id              bigserial   PRIMARY KEY,
    competition_id  bigint      NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    dog_id          uuid        NOT NULL REFERENCES dogs(id) ON DELETE CASCADE,
    events          text[]      NOT NULL,   -- この大会でのエントリー種目（複数選択）
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (competition_id, dog_id)          -- 1大会につき1犬1行（種目は配列でまとめて持つ）
);

CREATE OR REPLACE FUNCTION update_entries_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_entries_updated_at
BEFORE UPDATE ON entries
FOR EACH ROW EXECUTE FUNCTION update_entries_updated_at();

ALTER TABLE entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "entries_select" ON entries
    FOR SELECT USING (true);

-- 書き込みは「その犬の飼い主本人」または「その大会の運営者」のどちらか
CREATE POLICY "entries_write" ON entries
    FOR ALL TO authenticated
    USING (
        dog_id IN (SELECT id FROM dogs WHERE user_id = auth.uid())
        OR competition_id IN (SELECT id FROM competitions WHERE owner_user_id = auth.uid())
    )
    WITH CHECK (
        dog_id IN (SELECT id FROM dogs WHERE user_id = auth.uid())
        OR competition_id IN (SELECT id FROM competitions WHERE owner_user_id = auth.uid())
    );


-- ============================================================
-- 4. race_configs: 種目・クラス別コース設定（大会ごとに持つ）
-- ============================================================
CREATE TABLE race_configs (
    id              bigserial   PRIMARY KEY,
    competition_id  bigint      NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    event           text        NOT NULL,   -- "ビギナー" / "JP1.5" / "JP2.5" / "AG1" / "AG2" / "AG3"
    dog_class       text        NOT NULL,   -- "S" / "M" / "IM" / "L"
    course_len      numeric(7,2),
    std_time        numeric(6,2),
    limit_time      numeric(6,2),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (competition_id, event, dog_class)
);

CREATE TRIGGER trg_race_configs_updated_at
BEFORE UPDATE ON race_configs
FOR EACH ROW EXECUTE FUNCTION update_race_configs_updated_at();
-- ↑ 関数 update_race_configs_updated_at は既存のものをそのまま流用（DROPしていないため残っている）

ALTER TABLE race_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "race_configs_select" ON race_configs
    FOR SELECT USING (true);

CREATE POLICY "race_configs_write" ON race_configs
    FOR ALL TO authenticated
    USING (competition_id IN (SELECT id FROM competitions WHERE owner_user_id = auth.uid()))
    WITH CHECK (competition_id IN (SELECT id FROM competitions WHERE owner_user_id = auth.uid()));


-- ============================================================
-- 5. race_results: 出走ごとの成績
--    dog_id ではなく entry_id を参照する（「その大会にエントリー
--    している犬」にのみ結果を記録できるよう整合性を強化）。
-- ============================================================
CREATE TABLE race_results (
    id              bigserial   PRIMARY KEY,
    race_config_id  bigint      NOT NULL REFERENCES race_configs(id) ON DELETE CASCADE,
    entry_id        bigint      NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    time            numeric(6,2) DEFAULT 0,     -- 走行タイム (sec)。0 = 失格（未走行・途中棄権）
    fail            smallint    DEFAULT 0,
    refuse          smallint    DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (race_config_id, entry_id)
);

CREATE TRIGGER trg_race_results_updated_at
BEFORE UPDATE ON race_results
FOR EACH ROW EXECUTE FUNCTION update_race_results_updated_at();
-- ↑ 関数 update_race_results_updated_at も既存のものを流用

ALTER TABLE race_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "race_results_select" ON race_results
    FOR SELECT USING (true);

-- 結果の記録・修正は、その出走が属する大会の運営者のみ
-- （即時登録はスコアラー端末から運営者アカウントでログインして行う想定）
CREATE POLICY "race_results_write" ON race_results
    FOR ALL TO authenticated
    USING (
        race_config_id IN (
            SELECT rc.id FROM race_configs rc
            JOIN competitions c ON c.id = rc.competition_id
            WHERE c.owner_user_id = auth.uid()
        )
    )
    WITH CHECK (
        race_config_id IN (
            SELECT rc.id FROM race_configs rc
            JOIN competitions c ON c.id = rc.competition_id
            WHERE c.owner_user_id = auth.uid()
        )
    );


-- ============================================================
-- 6. 結果ビュー（旧 get_race_results を entry_id 対応に更新）
-- ============================================================
CREATE OR REPLACE FUNCTION get_race_results(p_race_config_id bigint)
RETURNS TABLE (
    result_id       bigint,
    entry_id        bigint,
    dog_id          uuid,
    user_id         uuid,
    user_name       text,
    dog_name        text,
    breed           text,
    dog_class       text,
    run_time        numeric,
    fail            smallint,
    refuse          smallint,
    deduct          numeric,
    speed           numeric,
    course_len      numeric,
    std_time        numeric,
    limit_time      numeric,
    turning_speed   numeric,
    updated_at      timestamptz
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        rr.id                                                           AS result_id,
        e.id                                                             AS entry_id,
        e.dog_id,
        d.user_id,
        (u.raw_user_meta_data->>'name')::text                          AS user_name,
        d.dog_name,
        d.breed,
        d.dog_class,
        rr.time                                                         AS run_time,
        rr.fail,
        rr.refuse,
        CASE
            WHEN rr.time = 0 THEN NULL
            ELSE round(
                ((rr.fail + rr.refuse) * 5
                 + GREATEST(0, rr.time - COALESCE(rc.std_time, 0)))::numeric,
                2
            )
        END                                                             AS deduct,
        CASE
            WHEN rr.time > 0 THEN round((rc.course_len / rr.time)::numeric, 2)
            ELSE NULL
        END                                                             AS speed,
        rc.course_len,
        rc.std_time,
        rc.limit_time,
        round((rc.course_len / NULLIF(rc.std_time, 0))::numeric, 2)   AS turning_speed,
        rr.updated_at
    FROM race_results rr
    JOIN race_configs rc ON rr.race_config_id = rc.id
    JOIN entries       e  ON e.id              = rr.entry_id
    JOIN dogs          d  ON d.id              = e.dog_id
    JOIN auth.users    u  ON u.id              = d.user_id
    WHERE rr.race_config_id = p_race_config_id;
$$;

GRANT EXECUTE ON FUNCTION get_race_results(bigint) TO authenticated, anon;


-- ============================================================
-- 7. 申込状況サマリー（旧 get_registration_summary を competition_id 対応に更新）
-- ============================================================
CREATE OR REPLACE FUNCTION get_registration_summary(p_competition_id bigint)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_entry_count  bigint;
    v_dog_count    bigint;
    v_event_counts jsonb;
BEGIN
    -- この大会への参加登録数（entries の件数 = 犬の頭数）
    SELECT COUNT(*) INTO v_entry_count FROM public.entries WHERE competition_id = p_competition_id;
    v_dog_count := v_entry_count;

    -- 種目別頭数
    SELECT jsonb_object_agg(event_name, cnt)
    INTO v_event_counts
    FROM (
        SELECT ev AS event_name, COUNT(*) AS cnt
        FROM public.entries, unnest(events) AS ev
        WHERE competition_id = p_competition_id
        GROUP BY ev
    ) sub;

    RETURN json_build_object(
        'entry_count',  v_entry_count,
        'dog_count',    v_dog_count,
        'event_counts', COALESCE(v_event_counts, '{}'::jsonb)
    );
END;
$$;

GRANT EXECUTE ON FUNCTION get_registration_summary(bigint) TO authenticated, anon;


-- ============================================================
-- 8. 大会ごとの参加者一覧（旧 get_participants_with_dogs を
--    competition_id 対応に更新。entry_id・events は dogs ではなく
--    entries から取得する）
-- ============================================================
CREATE OR REPLACE FUNCTION get_entries_with_dogs(p_competition_id bigint)
RETURNS TABLE (
    entry_id   bigint,
    dog_id     uuid,
    user_id    uuid,
    user_name  text,
    dog_name   text,
    breed      text,
    dog_class  text,
    events     text[]
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
        e.events
    FROM entries e
    JOIN dogs d ON d.id = e.dog_id
    JOIN auth.users u ON u.id = d.user_id
    WHERE e.competition_id = p_competition_id
    ORDER BY user_name, d.created_at;
$$;

GRANT EXECUTE ON FUNCTION get_entries_with_dogs(bigint) TO authenticated, anon;
