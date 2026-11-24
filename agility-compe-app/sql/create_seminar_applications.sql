-- ============================================================
-- セミナー申込（agility-events.puffin.tokyo.jp 内の申込フォーム）
-- 2026-11-19 作成。設計: MulmoClaude wiki「セミナー申込アプリ（設計）」
--
-- テーブル:
--   seminars                 セミナーごとの定員・受付中フラグ（events 1行に対応）
--   seminar_applications     申込（申込者1件 = 1行）
--   seminar_application_dogs 申込ごとの犬（複数頭）
-- 関数:
--   submit_seminar_application  申込の唯一の書き込み口（anon 可）
--   get_seminar_availability    残り枠など個人情報を含まない集計のみ（anon 可）
--   is_site_owner               RLS 用：呼び出し者がオーナーか
--
-- セキュリティ方針:
--   * 3テーブルとも RLS 有効。申込2テーブルは anon に一切の権限を与えない
--   * 閲覧・更新はオーナー（competitions.owner_user_id = auth.uid()）のみ
--   * 関数は REVOKE ALL FROM PUBLIC してから必要なロールにだけ GRANT
--   * SECURITY DEFINER 関数には SET search_path を付ける
-- ============================================================

-- ------------------------------------------------------------
-- オーナー判定
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_site_owner()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT auth.uid() IS NOT NULL
       AND EXISTS (SELECT 1 FROM public.competitions WHERE owner_user_id = auth.uid());
$$;

REVOKE ALL ON FUNCTION public.is_site_owner() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_site_owner() TO authenticated;

-- ------------------------------------------------------------
-- seminars
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.seminars (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id    bigint  NOT NULL UNIQUE REFERENCES public.events(id) ON DELETE CASCADE,
    capacity    integer NOT NULL CHECK (capacity > 0),
    accepting   boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    -- キャンセル待ちの上限件数。達したら submit_seminar_application が accepting=false にする（NULL=上限なし）
    waitlist_limit integer CHECK (waitlist_limit >= 1)
);

ALTER TABLE public.seminars ENABLE ROW LEVEL SECURITY;

-- 定員・受付中フラグは公開情報（静的サイトのビルドで anon キーから読む）
DROP POLICY IF EXISTS seminars_select ON public.seminars;
CREATE POLICY seminars_select ON public.seminars
    FOR SELECT USING (true);

DROP POLICY IF EXISTS seminars_owner_write ON public.seminars;
CREATE POLICY seminars_owner_write ON public.seminars
    FOR ALL TO authenticated
    USING (public.is_site_owner())
    WITH CHECK (public.is_site_owner());

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.seminars FROM anon;

-- ------------------------------------------------------------
-- seminar_applications
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.seminar_applications (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    seminar_id    bigint  NOT NULL REFERENCES public.seminars(id) ON DELETE CASCADE,
    name          text    NOT NULL CHECK (char_length(name) BETWEEN 1 AND 50),
    email         text    NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254),
    phone         text             CHECK (char_length(phone) <= 20),
    note          text             CHECK (char_length(note) <= 1000),
    dog_count     integer NOT NULL CHECK (dog_count BETWEEN 1 AND 5),
    status        text    NOT NULL CHECK (status IN ('confirmed', 'waitlist', 'cancelled')),
    contacted_at  timestamptz,
    admin_note    text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- 同じセミナーへの同じメールアドレスでの二重申込を防ぐ（取消済みは除外）
CREATE UNIQUE INDEX IF NOT EXISTS seminar_applications_unique_email
    ON public.seminar_applications (seminar_id, lower(email))
    WHERE status <> 'cancelled';

CREATE INDEX IF NOT EXISTS seminar_applications_seminar_idx
    ON public.seminar_applications (seminar_id, status, created_at);

ALTER TABLE public.seminar_applications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS seminar_applications_owner_all ON public.seminar_applications;
CREATE POLICY seminar_applications_owner_all ON public.seminar_applications
    FOR ALL TO authenticated
    USING (public.is_site_owner())
    WITH CHECK (public.is_site_owner());

REVOKE ALL ON public.seminar_applications FROM anon;

-- ------------------------------------------------------------
-- seminar_application_dogs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.seminar_application_dogs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id  uuid    NOT NULL REFERENCES public.seminar_applications(id) ON DELETE CASCADE,
    dog_name        text    NOT NULL CHECK (char_length(dog_name) BETWEEN 1 AND 50),
    breed           text             CHECK (char_length(breed) <= 50),
    dog_class       text    NOT NULL CHECK (dog_class IN ('S', 'M', 'IM', 'L')),
    level           text    NOT NULL CHECK (level IN ('ビギナー', '1度', '2度', '3度')),
    sort_order      integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS seminar_application_dogs_app_idx
    ON public.seminar_application_dogs (application_id, sort_order);

ALTER TABLE public.seminar_application_dogs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS seminar_application_dogs_owner_all ON public.seminar_application_dogs;
CREATE POLICY seminar_application_dogs_owner_all ON public.seminar_application_dogs
    FOR ALL TO authenticated
    USING (public.is_site_owner())
    WITH CHECK (public.is_site_owner());

REVOKE ALL ON public.seminar_application_dogs FROM anon;

-- ------------------------------------------------------------
-- 申込（唯一の書き込み口）
--   戻り値: {"status": "confirmed"|"waitlist", "waitlist_position": n}
--           または {"error": "not_found"|"closed"|"not_open"|"invalid"|"duplicate", "field": ...}
--   * seminars 行を FOR UPDATE でロックし、同時申込でも定員を超えないようにする
--   * 残り枠が足りない場合は申込全体をキャンセル待ちにする
--   * すでにキャンセル待ちがいる場合は、順番を守るため新規申込もキャンセル待ちにする
--   * キャンセル待ちが seminars.waitlist_limit 件に達したら受付を自動停止（accepting=false）
--   * 1申込あたりの犬は最大2頭（2026-11-22 に5頭から変更）
--   * p_website はボット対策のハニーポット（人間には見えない欄）。値があれば保存せず成功を装う
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.submit_seminar_application(
    p_event_id  bigint,
    p_name      text,
    p_email     text,
    p_phone     text,
    p_note      text,
    p_dogs      jsonb,
    p_website   text DEFAULT NULL
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_seminar   public.seminars%ROWTYPE;
    v_event     public.events%ROWTYPE;
    v_today     date := (now() AT TIME ZONE 'Asia/Tokyo')::date;
    v_name      text := btrim(coalesce(p_name, ''));
    v_email     text := lower(btrim(coalesce(p_email, '')));
    v_phone     text := nullif(btrim(coalesce(p_phone, '')), '');
    v_note      text := nullif(btrim(coalesce(p_note, '')), '');
    v_dog       jsonb;
    v_dog_count integer;
    v_used      integer;
    v_status    text;
    v_app_id    uuid;
    v_position  integer;
    v_idx       integer := 0;
BEGIN
    -- ハニーポット
    IF coalesce(p_website, '') <> '' THEN
        RETURN json_build_object('status', 'confirmed');
    END IF;

    SELECT * INTO v_seminar FROM public.seminars WHERE event_id = p_event_id FOR UPDATE;
    IF NOT FOUND THEN
        RETURN json_build_object('error', 'not_found');
    END IF;

    SELECT * INTO v_event FROM public.events WHERE id = p_event_id;
    IF NOT v_seminar.accepting OR coalesce(v_event.is_cancelled, false) THEN
        RETURN json_build_object('error', 'closed');
    END IF;
    IF v_event.registration_opens_on IS NOT NULL AND v_today < v_event.registration_opens_on THEN
        RETURN json_build_object('error', 'not_open');
    END IF;
    IF v_event.registration_deadline IS NOT NULL AND v_today > v_event.registration_deadline THEN
        RETURN json_build_object('error', 'closed');
    END IF;

    -- 入力チェック
    IF char_length(v_name) NOT BETWEEN 1 AND 50 THEN
        RETURN json_build_object('error', 'invalid', 'field', 'name');
    END IF;
    IF char_length(v_email) > 254 OR v_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' THEN
        RETURN json_build_object('error', 'invalid', 'field', 'email');
    END IF;
    IF v_phone IS NOT NULL AND (char_length(v_phone) > 20 OR v_phone !~ '^[-0-9０-９+()（）ー－ ]+$') THEN
        RETURN json_build_object('error', 'invalid', 'field', 'phone');
    END IF;
    IF v_note IS NOT NULL AND char_length(v_note) > 1000 THEN
        RETURN json_build_object('error', 'invalid', 'field', 'note');
    END IF;
    IF p_dogs IS NULL OR jsonb_typeof(p_dogs) <> 'array'
       OR jsonb_array_length(p_dogs) NOT BETWEEN 1 AND 2 THEN
        RETURN json_build_object('error', 'invalid', 'field', 'dogs');
    END IF;
    FOR v_dog IN SELECT value FROM jsonb_array_elements(p_dogs) LOOP
        IF jsonb_typeof(v_dog) <> 'object'
           OR char_length(btrim(coalesce(v_dog->>'dog_name', ''))) NOT BETWEEN 1 AND 50
           OR char_length(coalesce(v_dog->>'breed', '')) > 50
           OR coalesce(v_dog->>'dog_class', '') NOT IN ('S', 'M', 'IM', 'L')
           OR coalesce(v_dog->>'level', '') NOT IN ('ビギナー', '1度', '2度', '3度') THEN
            RETURN json_build_object('error', 'invalid', 'field', 'dogs');
        END IF;
    END LOOP;

    -- 二重申込
    IF EXISTS (
        SELECT 1 FROM public.seminar_applications
        WHERE seminar_id = v_seminar.id AND lower(email) = v_email AND status <> 'cancelled'
    ) THEN
        RETURN json_build_object('error', 'duplicate');
    END IF;

    -- 受付かキャンセル待ちかの判定
    v_dog_count := jsonb_array_length(p_dogs);
    SELECT coalesce(sum(dog_count), 0) INTO v_used
    FROM public.seminar_applications
    WHERE seminar_id = v_seminar.id AND status = 'confirmed';

    IF v_used + v_dog_count <= v_seminar.capacity
       AND NOT EXISTS (
           SELECT 1 FROM public.seminar_applications
           WHERE seminar_id = v_seminar.id AND status = 'waitlist'
       ) THEN
        v_status := 'confirmed';
    ELSE
        v_status := 'waitlist';
    END IF;

    INSERT INTO public.seminar_applications (seminar_id, name, email, phone, note, dog_count, status)
    VALUES (v_seminar.id, v_name, v_email, v_phone, v_note, v_dog_count, v_status)
    RETURNING id INTO v_app_id;

    FOR v_dog IN SELECT value FROM jsonb_array_elements(p_dogs) LOOP
        INSERT INTO public.seminar_application_dogs (application_id, dog_name, breed, dog_class, level, sort_order)
        VALUES (
            v_app_id,
            btrim(v_dog->>'dog_name'),
            nullif(btrim(coalesce(v_dog->>'breed', '')), ''),
            v_dog->>'dog_class',
            v_dog->>'level',
            v_idx
        );
        v_idx := v_idx + 1;
    END LOOP;

    IF v_status = 'waitlist' THEN
        SELECT count(*) INTO v_position
        FROM public.seminar_applications
        WHERE seminar_id = v_seminar.id AND status = 'waitlist';
        -- キャンセル待ちが上限に達したら受付を自動停止する（2026-11-24 追加）
        IF v_seminar.waitlist_limit IS NOT NULL AND v_position >= v_seminar.waitlist_limit THEN
            UPDATE public.seminars SET accepting = false WHERE id = v_seminar.id;
        END IF;
    END IF;

    RETURN json_build_object('status', v_status, 'waitlist_position', v_position);
EXCEPTION
    WHEN unique_violation THEN
        RETURN json_build_object('error', 'duplicate');
END;
$$;

REVOKE ALL ON FUNCTION public.submit_seminar_application(bigint, text, text, text, text, jsonb, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.submit_seminar_application(bigint, text, text, text, text, jsonb, text) TO anon, authenticated;

-- ------------------------------------------------------------
-- 残り枠（個人情報を含まない集計のみ）
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_seminar_availability(p_event_id bigint)
RETURNS json
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT json_build_object(
        'capacity',  s.capacity,
        'accepting', s.accepting,
        'confirmed', coalesce((SELECT sum(a.dog_count) FROM public.seminar_applications a
                               WHERE a.seminar_id = s.id AND a.status = 'confirmed'), 0),
        'remaining', greatest(s.capacity - coalesce((SELECT sum(a.dog_count) FROM public.seminar_applications a
                               WHERE a.seminar_id = s.id AND a.status = 'confirmed'), 0), 0),
        'waitlist',  (SELECT count(*) FROM public.seminar_applications a
                      WHERE a.seminar_id = s.id AND a.status = 'waitlist')
    )
    FROM public.seminars s
    WHERE s.event_id = p_event_id;
$$;

REVOKE ALL ON FUNCTION public.get_seminar_availability(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_seminar_availability(bigint) TO anon, authenticated;
