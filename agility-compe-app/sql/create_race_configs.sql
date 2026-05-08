-- 種目・クラス別コース設定テーブル
-- 種目（event）とクラス（dog_class）の組み合わせごとに1行持つ
CREATE TABLE race_configs (
    id          bigserial PRIMARY KEY,
    event       text        NOT NULL,   -- "ビギナー" / "JP1.5" / "JP2.5" / "AG1" / "AG2" / "AG3"
    dog_class   text        NOT NULL,   -- "S" / "M" / "IM" / "L"
    course_len  numeric(7,2),           -- コース全長 (m)
    std_time    numeric(6,2),           -- 標準タイム (sec)
    limit_time  numeric(6,2),           -- リミットタイム (sec)
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now(),
    UNIQUE (event, dog_class)
);

-- updated_at を自動更新するトリガー
CREATE OR REPLACE FUNCTION update_race_configs_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_race_configs_updated_at
BEFORE UPDATE ON race_configs
FOR EACH ROW EXECUTE FUNCTION update_race_configs_updated_at();

-- RLS: 読み取りは全員許可、書き込みはサービスロール（管理者）のみ
ALTER TABLE race_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "race_configs_select" ON race_configs
    FOR SELECT USING (true);

CREATE POLICY "race_configs_all_anon" ON race_configs
    FOR ALL USING (true) WITH CHECK (true);
