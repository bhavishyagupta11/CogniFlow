/**
 * Router Agent
 *
 * Analyzes the incoming question and decides:
 *   - what kind of question it is (factual / comparison / synthesis / procedural)
 *   - whether retrieval is needed
 *   - a rewritten search query optimized for the retriever
 *
 * This is the first agent in the pipeline and demonstrates query understanding
 * + query rewriting — both common interview topics for RAG systems.
 */

import "server-only";
import { chatJson } from "../llm";
import { RouterStep } from "./types";

interface RouterOutput {
  queryType: "factual" | "comparison" | "synthesis" | "procedural";
  rewrittenQuery: string;
  intentSummary: string;
  needsRetrieval: boolean;
}

const SYSTEM_PROMPT = `You are the Router agent in a multi-agent research assistant.
Your job is to analyze the user's question and produce a JSON plan that downstream agents will use.

Return JSON ONLY with this exact schema:
{
  "queryType": "factual" | "comparison" | "synthesis" | "procedural",
  "rewrittenQuery": "a search-optimized query (keywords, no question words)",
  "intentSummary": "one-sentence description of what the user wants",
  "needsRetrieval": true | false
}

Rules:
- "factual": a single fact lookup (e.g., "How many parameters does BERT-base have?")
- "comparison": contrasts two or more things (e.g., "BERT vs GPT-3")
- "synthesis": combines information across multiple sources (e.g., "How has attention evolved?")
- "procedural": asks how to do something step-by-step
- needsRetrieval is almost always true unless the question is a trivial greeting
- rewrittenQuery should be 3-8 keywords optimized for keyword search (TF-IDF)
- DO NOT include markdown code fences, just emit raw JSON`;

export async function runRouterAgent(
  question: string,
  stepId: string,
): Promise<RouterStep> {
  const startedAt = Date.now();
  let status: RouterStep["status"] = "running";
  let error: string | undefined;
  let output: RouterOutput;

  try {
    output = await chatJson<RouterOutput>(
      [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: question },
      ],
      { temperature: 0, maxTokens: 300 },
    );
    status = "completed";
  } catch (e: any) {
    // Fallback: use the raw question as the search query
    output = {
      queryType: "factual",
      rewrittenQuery: question,
      intentSummary: "Fallback: LLM router failed; using raw question.",
      needsRetrieval: true,
    };
    status = "error";
    error = e?.message ?? "Unknown router error";
  }

  const finishedAt = Date.now();
  return {
    id: stepId,
    agent: "router",
    label: "Analyzing question & rewriting query",
    startedAt,
    finishedAt,
    durationMs: finishedAt - startedAt,
    status,
    error,
    input: { question },
    output,
  };
}
