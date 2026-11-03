import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { getCompetitionId } from "@/lib/competition";
import { addDog, deleteDog, saveEntry, updateDog } from "./actions";
import { DOG_CLASSES, MAX_DOGS, type Dog, type RaceConfig } from "@/lib/types";
import { barDownOptions } from "@/lib/barDown";

export default async function DogsPage({
  searchParams,
}: {
  searchParams: Promise<{ selected?: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login");
  }

  const competitionId = getCompetitionId();
  const { selected } = await searchParams;

  const [{ data: dogs }, { data: competition }, { data: raceConfigs }] =
    await Promise.all([
      supabase
        .from("dogs")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at")
        .returns<Dog[]>(),
      supabase
        .from("competitions")
        .select("event_fees")
        .eq("id", competitionId)
        .single(),
      supabase
        .from("race_configs")
        .select("*")
        .eq("competition_id", competitionId)
        .returns<RaceConfig[]>(),
    ]);

  const dogList = dogs ?? [];
  const eventNames: string[] = (
    (competition?.event_fees as { name: string; fee: number }[] | null) ?? []
  ).map((e) => e.name);

  const dogIds = dogList.map((d) => d.id);
  const { data: entries } = dogIds.length
    ? await supabase
        .from("entries")
        .select("dog_id, events, bar_down_requests")
        .eq("competition_id", competitionId)
        .in("dog_id", dogIds)
    : { data: [] as { dog_id: string; events: string[]; bar_down_requests: Record<string, number> }[] };

  const entriesByDog = new Map(
    (entries ?? []).map((e) => [e.dog_id, e]),
  );

  const selectedDog = dogList.find((d) => d.id === selected) ?? null;

  // (event, dog_class) -> bar_height のルックアップ
  const barHeightByKey = new Map<string, number | null>();
  for (const rc of raceConfigs ?? []) {
    barHeightByKey.set(`${rc.event}__${rc.dog_class}`, rc.bar_height);
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col gap-4 p-6">
      <h1 className="text-xl font-bold">犬情報</h1>
      <p className="text-sm text-gray-500">
        参加種目の登録・変更、削除は選択ボタンで
      </p>

      <ul className="flex flex-col gap-2">
        {dogList.length === 0 && (
          <li className="text-sm text-gray-500">まだ犬が登録されていません。</li>
        )}
        {dogList.map((dog) => {
          const entry = entriesByDog.get(dog.id);
          const eventsStr = entry?.events?.join("、") || "未選択";
          const isSelected = dog.id === selected;
          return (
            <li key={dog.id} className="rounded border p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-semibold">
                    {isSelected ? "✏️ " : ""}
                    {dog.dog_name}　{dog.breed}
                  </p>
                  <p className="text-sm text-gray-500">
                    クラス: {dog.dog_class}　／　参加種目: {eventsStr}
                  </p>
                </div>
                {!isSelected && (
                  <Link
                    href={`/dogs?selected=${dog.id}`}
                    className="shrink-0 rounded border px-3 py-1 text-sm"
                  >
                    選択
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {selectedDog && (
        <>
          <hr />
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">「{selectedDog.dog_name}」を編集</h2>
            <form action={updateDog} className="flex flex-col gap-2">
              <input type="hidden" name="dog_id" value={selectedDog.id} />
              <input
                name="dog_name"
                defaultValue={selectedDog.dog_name}
                placeholder="犬名"
                required
                className="rounded border px-3 py-2"
              />
              <input
                name="breed"
                defaultValue={selectedDog.breed}
                placeholder="犬種"
                required
                className="rounded border px-3 py-2"
              />
              <div className="flex gap-3">
                {DOG_CLASSES.map((c) => (
                  <label key={c} className="flex items-center gap-1 text-sm">
                    <input
                      type="radio"
                      name="dog_class"
                      value={c}
                      defaultChecked={selectedDog.dog_class === c}
                    />
                    {c}
                  </label>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="flex-1 rounded bg-blue-600 px-4 py-2 font-semibold text-white"
                >
                  変更する
                </button>
              </div>
            </form>
            <form action={deleteDog}>
              <input type="hidden" name="dog_id" value={selectedDog.id} />
              <button
                type="submit"
                className="w-full rounded border border-red-400 px-4 py-2 font-semibold text-red-600"
              >
                削除する
              </button>
            </form>
            <Link href="/dogs" className="text-center text-sm text-blue-600 underline">
              キャンセル
            </Link>
          </section>

          <hr />
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">参加種目の選択</h2>
            <form action={saveEntry} className="flex flex-col gap-3 rounded border p-3">
              <input type="hidden" name="dog_id" value={selectedDog.id} />
              {eventNames.map((event) => {
                const entry = entriesByDog.get(selectedDog.id);
                const checked = entry?.events?.includes(event) ?? false;
                const defaultBarHeight =
                  barHeightByKey.get(`${event}__${selectedDog.dog_class}`) ?? null;
                const requestedHeight = entry?.bar_down_requests?.[event];
                const options = defaultBarHeight ? barDownOptions(defaultBarHeight) : [];

                return (
                  <div key={event} className="flex flex-col gap-1 border-b pb-2 last:border-b-0">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        name={`event__${event}`}
                        defaultChecked={checked}
                      />
                      {event}
                    </label>
                    {defaultBarHeight != null && (
                      <label className="ml-6 flex items-center gap-2 text-sm text-gray-600">
                        バーダウン希望（既定 {defaultBarHeight}cm）:
                        <select
                          name={`bardown__${event}`}
                          defaultValue={requestedHeight ?? ""}
                          className="rounded border px-2 py-1"
                        >
                          <option value="">希望なし（既定の高さ）</option>
                          {options.map((h) => (
                            <option key={h} value={h}>
                              {h}cm
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                  </div>
                );
              })}
              <button
                type="submit"
                className="rounded bg-blue-600 px-4 py-2 font-semibold text-white"
              >
                この犬の参加種目を保存
              </button>
            </form>
          </section>
        </>
      )}

      {!selectedDog && (
        <>
          <hr />
          <section className="flex flex-col gap-3">
            <h2 className="font-semibold">犬を追加登録する</h2>
            <p className="text-sm text-gray-500">
              登録済み: {dogList.length} 頭 / 最大 {MAX_DOGS} 頭
            </p>
            {dogList.length >= MAX_DOGS ? (
              <p className="text-sm text-yellow-700">
                登録できる犬は最大 {MAX_DOGS} 頭までです。
              </p>
            ) : (
              <form action={addDog} className="flex flex-col gap-2">
                <input
                  name="dog_name"
                  placeholder="犬名"
                  required
                  className="rounded border px-3 py-2"
                />
                <input
                  name="breed"
                  placeholder="犬種"
                  required
                  className="rounded border px-3 py-2"
                />
                <div className="flex gap-3">
                  {DOG_CLASSES.map((c, i) => (
                    <label key={c} className="flex items-center gap-1 text-sm">
                      <input
                        type="radio"
                        name="dog_class"
                        value={c}
                        defaultChecked={i === 0}
                      />
                      {c}
                    </label>
                  ))}
                </div>
                <button
                  type="submit"
                  className="rounded bg-blue-600 px-4 py-2 font-semibold text-white"
                >
                  登録する
                </button>
              </form>
            )}
          </section>
        </>
      )}

      <hr />
      <Link href="/" className="text-center text-sm text-blue-600 underline">
        ホームに戻る
      </Link>
    </main>
  );
}
