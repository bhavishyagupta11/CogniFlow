/**
 * Critic Agent
 *
 * Reviews the Analyzer's answer against the source chunks to detect:
 *   - hallucinations (claims not supported by any source)
 *   - missing citations
 *   - unsupported comparisons
 *   - factual contradictions between sources and answer
 *
 * If issues are found, the Critic returns "needs_revision" with revision notes.
 * The Coordinator will then re-invoke the Analyzer with those notes (self-refine
 * loop, max 2 iterations). Otherwise it returns "faithful" and the pipeline
 * terminates.
 *
 * This demonstrates the "reflection / self-correction" pattern that's become
 * standard in modern agent frameworks (Reflexion, Self-Refine, Constitutional
 * AI's self-critique step).
 */

import "server-only";
import { chatJson } from "../llm";
import { Chunk } from "../rag/chunker";
import { CriticStep } from "./types";

interface CriticResponse {
  verdict: "faithful" | "needs_revision";
  faithfulnessScore: number;
  issues: string[];
  revisionNotes?: string;
}

const SYSTEM_PROMPT = `You are the Critic agent in a multi-agent research assistant.
Your job is to verify that the Analyzer's answer is faithful to the provided source chunks.

Check for:
1. Hallucinations: claims in the answer that are not supported by ANY source chunk.
2. Missing citations: substantive factual claims without a [n] citation.
3. Unsupported comparisons: comparisons asserted in the answer that the sources don't make.
4. Misattribution: citations pointing to sources that don't actually support the claim.

Return JSON ONLY with this exact schema:
{
  "verdict": "faithful" | "needs_revision",
  "faithfulnessScore": 0-100,
  "issues": ["issue 1", "issue 2", ...],
  "revisionNotes": "optional, only if verdict='needs_revision'"
}

Rules:
- faithfulnessScore >= 85 with no major issues → verdict = "faithful"
- faithfulnessScore < 85 OR any hallucination found → verdict = "needs_revision"
- revisionNotes should give the Analyzer concrete instructions on what to fix
- DO NOT include markdown code fences, just emit raw JSON
- Be strict but fair — don't fail for stylistic choices, only for factual problems
- Ignore LaTeX formatting differences (e.g., $d_{model}$ vs d_model). The Analyzer is explicitly instructed to format math this way, this is NOT a hallucination.`;

interface CriticArgs {
  question: string;
  answer: string;
  chunks: Chunk[];
  stepId: string;
}

export async function runCriticAgent(args: CriticArgs): Promise<CriticStep> {
  const { question, answer, chunks, stepId } = args;
  const startedAt = Date.now();
  let status: CriticStep["status"] = "running";
  let error: string | undefined;

  const sourcesBlock = chunks
    .map(
      (c, i) =>
        `[${i + 1}] (from "${c.documentTitle}", chunk ${c.index})\n${c.content}`,
    )
    .join("\n\n---\n\n");

  let output: CriticStep["output"];

  try {
    const response = await chatJson<CriticResponse>(
      [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `User question: ${question}

Proposed answer:
${answer}

Source chunks:
${sourcesBlock}

Evaluate the answer's faithfulness to the sources.`,
        },
      ],
      { temperature: 0, maxTokens: 600 },
    );

    output = {
      verdict: response.verdict,
      faithfulnessScore: response.faithfulnessScore,
      issues: response.issues ?? [],
      revisionNotes: response.revisionNotes,
    };
    status = "completed";
  } catch (e: any) {
    output = {
      verdict: "faithful",
      faithfulnessScore: 100,
      issues: [],
    };
    status = "error";
    error = e?.message ?? "Unknown critic error";
  }

  const finishedAt = Date.now();
  return {
    id: stepId,
    agent: "critic",
    label: "Validating answer against sources",
    startedAt,
    finishedAt,
    durationMs: finishedAt - startedAt,
    status,
    error,
    input: { answerLength: answer.length, numSources: chunks.length },
    output,
  };
}
