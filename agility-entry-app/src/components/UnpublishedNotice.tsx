import { DEFAULT_UNPUBLISHED_MESSAGE } from "@/lib/publish";

/**
 * 大会が非公開（competitions.is_published = false）の間、
 * 参加登録アプリの代わりに表示する準備中メッセージ画面。
 * 管理画面で次回大会の情報を編集している間、外部に内容を見せないための表示。
 */
export function UnpublishedNotice({ message }: { message: string | null }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
      <p className="rounded border border-gray-300 bg-gray-50 px-4 py-6 text-center whitespace-pre-wrap">
        {message || DEFAULT_UNPUBLISHED_MESSAGE}
      </p>
    </main>
  );
}
