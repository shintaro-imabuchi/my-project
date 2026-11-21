-- セミナー申込：1申込あたりの犬の上限を5頭→2頭に変更（2026-11-22）
-- submit_seminar_application を置き換えるだけ。テーブル・既存データは変更しない
-- （テーブルの CHECK (dog_count BETWEEN 1 AND 5) はそのまま。上限の判定は関数側で行う）

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
    END IF;

    RETURN json_build_object('status', v_status, 'waitlist_position', v_position);
EXCEPTION
    WHEN unique_violation THEN
        RETURN json_build_object('error', 'duplicate');
END;
$$;

REVOKE ALL ON FUNCTION public.submit_seminar_application(bigint, text, text, text, text, jsonb, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.submit_seminar_application(bigint, text, text, text, text, jsonb, text) TO anon, authenticated;
