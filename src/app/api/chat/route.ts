/**
 * POST /api/chat
 *
 * Body: { question: string }
 * Response: AgentRunResult (see src/lib/agents/types.ts)
 *
 * This is the single endpoint the frontend calls. It runs the full multi-agent
 * pipeline server-side and returns the answer + agent trace + sources.
 */

import "server-only";
import { NextRequest, NextResponse } from "next/server";
import { runMultiAgentPipeline } from "@/lib/agents/coordinator";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: NextRequest) {
  let body: { question?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body" },
      { status: 400 },
    );
  }

  const question = (body.question ?? "").trim();
  if (!question) {
    return NextResponse.json(
      { error: "Missing 'question' field" },
      { status: 400 },
    );
  }
  if (question.length > 1000) {
    return NextResponse.json(
      { error: "Question too long (max 1000 chars)" },
      { status: 400 },
    );
  }

  try {
    const result = await runMultiAgentPipeline(question);
    return NextResponse.json(result);
  } catch (e: any) {
    console.error("[/api/chat] pipeline error:", e);
    return NextResponse.json(
      { error: e?.message ?? "Pipeline failed" },
      { status: 500 },
    );
  }
}

export async function GET() {
  return NextResponse.json({
    ok: true,
    message:
      "Multi-Agent RAG endpoint. POST a JSON body { question: string } to run the pipeline.",
  });
}
