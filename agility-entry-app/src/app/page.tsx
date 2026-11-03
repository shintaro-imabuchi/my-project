import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { getCompetition, getLoginMessage } from "@/lib/competition";
import { logout } from "@/app/logout/actions";

// Streamlit版（pages/03_events.py）の「競技会・練習会などの一覧を見る」に
// 相当するリンク先。公開開催情報一覧（静的サイト）へ誘導する。
const EVENTS_LIST_URL = "https://agility-events.puffin.tokyo.jp/";

export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const [competition, loginMessage] = await Promise.all([
    getCompetition(),
    getLoginMessage(),
  ]);
  const title = loginMessage || competition?.name || "参加登録システム";

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

        {competition?.guideline_url && (
          <a
            href={competition.guideline_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border px-4 py-3 text-center font-semibold"
          >
            開催要綱を見る
          </a>
        )}

        <a
          href={EVENTS_LIST_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded border px-4 py-3 text-center font-semibold"
        >
          競技会・練習会などの一覧を見る
        </a>

        {competition?.top_image_url && (
          // eslint-disable-next-line @next/next/no-img-element -- 外部URLの動的画像のためnext/imageの設定は省略
          <img
            src={competition.top_image_url}
            alt=""
            className="w-full rounded"
          />
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

      <Link
        href="/status"
        className="rounded border px-4 py-3 text-center font-semibold"
      >
        申し込み状況を見る
      </Link>

      {competition?.notice_url && (
        <a
          href={competition.notice_url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded border px-4 py-3 text-center font-semibold"
        >
          練習会実施のご案内を見る
        </a>
      )}

      {competition?.home_info_message && (
        <p className="rounded border border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-900 whitespace-pre-wrap">
          {competition.home_info_message}
        </p>
      )}

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
