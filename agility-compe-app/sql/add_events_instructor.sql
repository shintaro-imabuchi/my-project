-- events に講師名（表示用テキスト）を追加
-- 2026-11-19 追加。セミナー申込ページの「開催日」の前の行に表示する
ALTER TABLE public.events
    ADD COLUMN IF NOT EXISTS instructor text
    CHECK (char_length(instructor) <= 100);
