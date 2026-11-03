import { redirect } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { getCompetition, getCompetitionId } from "@/lib/competition";
import { DOG_CLASSES, type EntryWithDog, type RegistrationSummary } from "@/lib/types";

export default async function StatusPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login");
  }

  const competitionId = getCompetitionId();
  const [competition, summaryRes, participantsRes] = await Promise.all([
    getCompetition(),
    supabase.rpc("get_registration_summary", {
      p_competition_id: competitionId,
    }),
    supabase.rpc("get_entries_with_dogs", { p_competition_id: competitionId }),
  ]);

  const summary = summaryRes.data as RegistrationSummary | null;
  const participants = (participantsRes.data as EntryWithDog[] | null) ?? [];
  const eventNames: string[] = (competition?.event_fees ?? []).map((e) => e.name);

  // 種目ごとの頭数・クラス別頭数（Streamlit版 pages/02_registration_status.py の
  // rows / totals と同じ集計ロジック。1頭が複数種目に出る場合は種目ごとに
  // それぞれカウントするため、クラス別合計は「頭数」の延べ数になる）。
  const rows = eventNames.map((event) => {
    const classCounts = Object.fromEntries(
      DOG_CLASSES.map((cls) => [
        cls,
        participants.filter(
          (p) => p.events?.includes(event) && p.dog_class === cls,
        ).length,
      ]),
    ) as Record<(typeof DOG_CLASSES)[number], number>;
    return { event, total: summary?.event_counts?.[event] ?? 0, classCounts };
  });
  const totals = {
    total: rows.reduce((sum, r) => sum + r.total, 0),
    classCounts: Object.fromEntries(
      DOG_CLASSES.map((cls) => [
        cls,
        rows.reduce((sum, r) => sum + r.classCounts[cls], 0),
      ]),
    ) as Record<(typeof DOG_CLASSES)[number], number>,
  };

  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col gap-4 p-6">
      <h1 className="text-xl font-bold">申し込み状況</h1>

      {!summary ? (
        <p className="text-sm text-gray-500">集計中にエラーが発生しました。</p>
      ) : (
        <>
          <div className="flex gap-4">
            <div className="flex-1 rounded border p-4 text-center">
              <p className="text-sm text-gray-500">参加登録数</p>
              <p className="text-2xl font-bold">{summary.entry_count} 件</p>
            </div>
            <div className="flex-1 rounded border p-4 text-center">
              <p className="text-sm text-gray-500">登録済み犬数</p>
              <p className="text-2xl font-bold">{summary.dog_count} 頭</p>
            </div>
          </div>

          <h2 className="font-semibold">種目別エントリー数</h2>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b">
                <th className="py-1 text-left">種目</th>
                <th className="py-1 text-right">頭数</th>
                {DOG_CLASSES.map((c) => (
                  <th key={c} className="py-1 text-right">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ event, total, classCounts }) => (
                <tr key={event} className="border-b">
                  <td className="py-1">{event}</td>
                  <td className="py-1 text-right">{total}</td>
                  {DOG_CLASSES.map((c) => (
                    <td key={c} className="py-1 text-right">
                      {classCounts[c]}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="py-1">合計</td>
                <td className="py-1 text-right">{totals.total}</td>
                {DOG_CLASSES.map((c) => (
                  <td key={c} className="py-1 text-right">
                    {totals.classCounts[c]}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </>
      )}

      <hr />
      <Link href="/" className="text-center text-sm text-blue-600 underline">
        ホームに戻る
      </Link>
    </main>
  );
}
