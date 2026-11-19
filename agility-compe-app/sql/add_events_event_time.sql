-- events に予定時間（表示用テキスト、例: "8:30〜16:30"）を追加
-- 2026-11-19 追加。セミナー申込ページの「開催日」の次の行に表示する
ALTER TABLE public.events
    ADD COLUMN IF NOT EXISTS event_time text
    CHECK (char_length(event_time) <= 50);
