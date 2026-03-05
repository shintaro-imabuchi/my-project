-- settings テーブル: アプリ全体の設定値を管理する
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT    PRIMARY KEY,
    value BOOLEAN NOT NULL
);

-- 初期値: 新規登録を受け付ける状態でINSERT
INSERT INTO settings (key, value)
VALUES ('registration_open', true)
ON CONFLICT (key) DO NOTHING;

-- RLS: 読み取りは全員許可、書き込みはanon/authenticatedに許可
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "settings_select" ON settings
    FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "settings_update" ON settings
    FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
