import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { getCompetition } from "@/lib/competition";
import { logout } from "@/app/logout/actions";

export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const competition = await getCompetition();
  const title = competition?.name ?? "参加登録システム";

  if (!user) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
        <h1 className="text-xl font-bold">{title} 参加登録</h1>

        <Link
          href="/login"
          className="rounded bg-blue-600 px-4 py-3 text-center font-semibold text-white"
        >
          ログイン
        </Link>

        {competition?.registration_open ? (
          <Link
            href="/register"
            className="rounded border px-4 py-3 text-center font-semibold"
          >
            新規登録
          </Link>
        ) : (
          <p className="rounded border border-yellow-400 bg-yellow-50 px-4 py-3 text-center text-sm">
            新規登録を締め切りました
          </p>
        )}
      </main>
    );
  }

  const name = (user.user_metadata?.name as string | undefined) ?? "";

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="rounded bg-green-50 px-4 py-3 text-green-800">
        ようこそ、{name} さん！
      </p>

      <Link
        href="/dogs"
        className="rounded bg-blue-600 px-4 py-3 text-center font-semibold text-white"
      >
        犬情報の登録・変更・削除
      </Link>

      <form action={logout}>
        <button
          type="submit"
          className="w-full rounded border px-4 py-3 text-center font-semibold"
        >
          ログアウト
        </button>
      </form>
    </main>
  );
}
