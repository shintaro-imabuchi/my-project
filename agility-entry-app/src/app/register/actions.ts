"use server";

import { createClient } from "@/lib/supabase/server";

export interface FormState {
  error: string | null;
  success: string | null;
}

export async function signUp(
  _prevState: FormState,
  formData: FormData,
): Promise<FormState> {
  const name = String(formData.get("name") ?? "");
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (!name || !email || !password) {
    return { error: "すべての項目を入力してください。", success: null };
  }
  if (password.length < 6) {
    return { error: "パスワードは6文字以上で入力してください。", success: null };
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { name } },
  });

  if (error) {
    const msg = error.message.toLowerCase();
    if (msg.includes("already registered") || msg.includes("already been registered")) {
      return {
        error: "このメールアドレスはすでに登録されています。別のメールアドレスで登録してください。",
        success: null,
      };
    }
    return { error: `登録に失敗しました: ${error.message}`, success: null };
  }

  if (data.session) {
    // メール確認が不要な設定の場合は即ログイン状態になる
    return { error: null, success: "REDIRECT" };
  }

  return {
    error: null,
    success: "確認メールを送信しました。メール内のリンクをクリックしてからログインしてください。",
  };
}
