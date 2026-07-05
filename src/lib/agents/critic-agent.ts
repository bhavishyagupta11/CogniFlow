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
import { CriticStep, CriticOutputSchema } from "./types";
import { Result, success, failure } from "../result";
import { logger } from "../logger";
import { ParsingError, BaseApplicationError } from "../errors";

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
  requestId: string;
}

export async function runCriticAgent(args: CriticArgs): Promise<Result<CriticStep>> {
  const { question, answer, chunks, stepId, requestId } = args;
  const startedAt = Date.now();
  logger.info("Starting Critic Agent", { requestId, agent: "critic", stepId, numSources: chunks.length });

  const sourcesBlock = chunks
    .map(
      (c, i) =>
        `[${i + 1}] (from "${c.documentTitle}", chunk ${c.index})\n${c.content}`,
    )
    .join("\n\n---\n\n");

  try {
    const rawOutput = await chatJson<unknown>(
      [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `User question: ${question}\n\nProposed answer:\n${answer}\n\nSource chunks:\n${sourcesBlock}\n\nEvaluate the answer's faithfulness to the sources.`,
        },
      ],
      { temperature: 0, maxTokens: 600 },
      requestId,
      "critic"
    );

    const parseResult = CriticOutputSchema.safeParse(rawOutput);
    
    if (!parseResult.success) {
      const errorMsg = parseResult.error.errors.map(e => `${e.path.join(".")}: ${e.message}`).join(", ");
      logger.warn("Critic validation failed", { requestId, agent: "critic", errors: errorMsg });
      throw new ParsingError("CRITIC_SCHEMA_MISMATCH", `Critic output violated schema: ${errorMsg}`, { requestId, agent: "critic" });
    }

    const output = parseResult.data;
    const finishedAt = Date.now();
    
    logger.info("Critic Agent completed successfully", { 
      requestId, agent: "critic", durationMs: finishedAt - startedAt, verdict: output.verdict 
    });

    return success({
      id: stepId,
      agent: "critic",
      label: "Validating answer against sources",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "completed",
      input: { answerLength: answer.length, numSources: chunks.length },
      output,
    });
  } catch (e: any) {
    if (e instanceof BaseApplicationError) {
      return failure(e);
    }
    return failure(
      new ParsingError("CRITIC_UNEXPECTED_ERROR", e?.message ?? "Unknown critic error", { requestId, agent: "critic" }, e)
    );
  }
}
