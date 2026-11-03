// `output: "standalone"` の既知の制約への対応。
// standaloneビルドには public/ と .next/static が自動で含まれないため、
// ビルド後に手動でコピーする（Next.js公式ドキュメント記載の既知の手順）。
// Node標準モジュールのみで実装し、Windows/Linuxどちらでも動くようにしている。
import { cpSync, existsSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const standaloneDir = path.join(root, ".next", "standalone");

if (!existsSync(standaloneDir)) {
  console.error(
    "[copy-standalone-assets] .next/standalone が見つかりません。next.config.ts の output: 'standalone' が有効か確認してください。",
  );
  process.exit(1);
}

const publicSrc = path.join(root, "public");
const publicDest = path.join(standaloneDir, "public");
if (existsSync(publicSrc)) {
  cpSync(publicSrc, publicDest, { recursive: true });
}

const staticSrc = path.join(root, ".next", "static");
const staticDest = path.join(standaloneDir, ".next", "static");
if (existsSync(staticSrc)) {
  cpSync(staticSrc, staticDest, { recursive: true });
}

console.log("[copy-standalone-assets] public/ と .next/static を .next/standalone にコピーしました。");
