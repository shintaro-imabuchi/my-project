-- settings.value を BOOLEAN から JSONB に変更する
-- registration_open の値(true/false)はJSONBでもそのまま読み書きできる
ALTER TABLE settings ALTER COLUMN value TYPE JSONB USING to_jsonb(value);
ALTER TABLE settings ALTER COLUMN value DROP NOT NULL;

-- upsert (INSERT ON CONFLICT) を使うため INSERT ポリシーを追加
CREATE POLICY "settings_insert" ON settings
    FOR INSERT TO anon, authenticated WITH CHECK (true);

-- event_fees の初期行を挿入（既存行があればスキップ）
INSERT INTO settings (key, value)
VALUES ('event_fees', '[
    {"name": "ビギナー", "fee": 2000},
    {"name": "JP1.5",   "fee": 3000},
    {"name": "JP2.5",   "fee": 3000},
    {"name": "AG1",     "fee": 3000},
    {"name": "AG2",     "fee": 3000},
    {"name": "AG3",     "fee": 3000}
]'::jsonb)
ON CONFLICT (key) DO NOTHING;
