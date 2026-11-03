"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signUp, type FormState } from "./actions";

const initialState: FormState = { error: null, success: null };

export default function RegisterPage() {
  const [state, formAction, pending] = useActionState(signUp, initialState);
  const router = useRouter();

  useEffect(() => {
    if (state.success === "REDIRECT") {
      router.push("/");
    }
  }, [state.success, router]);

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-6">
      <h1 className="text-xl font-bold">新規登録</h1>

      <form action={formAction} className="flex flex-col gap-3">
        <input
          name="name"
          placeholder="氏名"
          required
          className="rounded border px-3 py-2"
        />
        <input
          name="email"
          type="email"
          placeholder="メールアドレス"
          required
          className="rounded border px-3 py-2"
        />
        <input
          name="password"
          type="password"
          placeholder="パスワード（6文字以上）"
          required
          className="rounded border px-3 py-2"
        />
        {state.error && <p className="text-sm text-red-600">{state.error}</p>}
        {state.success && state.success !== "REDIRECT" && (
          <p className="text-sm text-green-700">{state.success}</p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-blue-600 px-4 py-2 font-semibold text-white disabled:opacity-50"
        >
          {pending ? "登録中..." : "登録する"}
        </button>
      </form>

      <Link href="/" className="text-center text-sm text-blue-600 underline">
        戻る
      </Link>
    </main>
  );
}
