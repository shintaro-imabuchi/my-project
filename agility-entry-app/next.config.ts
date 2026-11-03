import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Renderのようなコンテナ型ホストで動かすための自己完結ビルド。
  output: "standalone",
  // このアプリはほぼ全ページがCookie（ログインセッション）に依存する
  // 動的コンテンツのため、Cache Components（静的プリレンダリング前提の
  // 新機能）は有効にしない。全ページ動的でよい。
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
