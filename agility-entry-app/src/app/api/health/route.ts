// RenderのHealth Check Path用。常に200を返すだけでよい。
export async function GET() {
  return new Response("ok", { status: 200 });
}
