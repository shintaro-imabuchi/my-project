-- 種目・クラス別成績テーブル
-- race_configs の1行に対して、対象参加者（user_id）ごとに1行持つ
CREATE TABLE race_results (
    id              bigserial   PRIMARY KEY,
    race_config_id  bigint      NOT NULL REFERENCES race_configs(id) ON DELETE CASCADE,
    user_id         uuid        NOT NULL REFERENCES auth.users(id),
    time            numeric(6,2) DEFAULT 0,     -- 走行タイム (sec)。0 = 失格（未走行・途中棄権）
    fail            smallint    DEFAULT 0,       -- 失敗数
    refuse          smallint    DEFAULT 0,       -- 拒絶数
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (race_config_id, user_id)            -- 同一種目・クラスに同一参加者は1行のみ
);

-- updated_at を自動更新するトリガー
CREATE OR REPLACE FUNCTION update_race_results_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_race_results_updated_at
BEFORE UPDATE ON race_results
FOR EACH ROW EXECUTE FUNCTION update_race_results_updated_at();

-- RLS: 読み取りは全員許可、書き込みはサービスロール（管理者）のみ
ALTER TABLE race_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "race_results_select" ON race_results
    FOR SELECT USING (true);

CREATE POLICY "race_results_all_anon" ON race_results
    FOR ALL USING (true) WITH CHECK (true);
