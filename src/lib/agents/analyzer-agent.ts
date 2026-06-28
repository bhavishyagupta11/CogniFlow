/**
 * Analyzer Agent
 *
 * Given the user's question and the reranked source chunks, synthesizes a
 * grounded answer with inline citations [1], [2], ... matching the indices in
 * the sources list. This is the "generation" half of RAG.
 *
 * If the Critic agent flags the previous answer as needing revision, this
 * agent is called again with the critic's notes — implementing a self-refine
 * loop. This is a key interview talking point (reflection / self-correction
 * pattern in agentic systems).
 */

import "server-only";
import { chat } from "../llm";
import { Chunk } from "../rag/chunker";
import { AnalyzerStep } from "./types";

const SYSTEM_PROMPT = `You are the Analyzer agent in a multi-agent research assistant.
Your job is to synthesize a grounded answer to the user's question using ONLY the provided source chunks.

Rules:
- Answer in clear, well-structured prose. Use short paragraphs or bullet points where helpful.
- Cite sources inline using [1], [2], ... notation matching the source index provided. Attach citations directly to the specific facts they support, rather than bunching them at the end of a long list.
- NEVER include information that is not supported by the sources. If the sources don't fully answer the question, say so explicitly.
- If asked to compare, structure the answer as a comparison.
- If asked for a procedure, structure the answer as numbered steps.
- Keep the answer focused and concise (3-6 short paragraphs max).
- If you receive "Revision notes" from a Critic agent, address each note explicitly when rewriting.
- Format ALL mathematical variables, formulas, and expressions using LaTeX delimiters ($...$ for inline, $$...$$ for block). Always use proper LaTeX brace syntax for multi-character subscripts (e.g. $d_{model}$ instead of $d_model$, $d_k$ instead of d_k).

CONTENT FORMATTING GUIDELINES:
- For narrative/research paper content (claims, findings, methodologies): Write in natural prose paragraphs or standard bullet points.
- For resume/CV/profile-style content (dense lists of skills, tools, dates, roles): Do NOT cram multiple unrelated categories into a single bullet or run-on sentence. Instead, group related skills/tools under clear sub-headers (e.g., "Languages", "Frameworks"). Ensure each bullet contains only one tightly-related cluster of facts and is reasonably short (avoid multi-line wrapped text). Do not invent categories if the source does not support it.`;

interface AnalyzerArgs {
  question: string;
  queryType: string;
  chunks: Chunk[];
  iteration: number;
  revisionNotes?: string;
  stepId: string;
}

export async function runAnalyzerAgent(
  args: AnalyzerArgs,
): Promise<AnalyzerStep> {
  const { question, queryType, chunks, iteration, revisionNotes, stepId } =
    args;
  const startedAt = Date.now();
  let status: AnalyzerStep["status"] = "running";
  let error: string | undefined;
  let answer = "";

  const sourcesBlock = chunks
    .map(
      (c, i) =>
        `[${i + 1}] (from "${c.documentTitle}", chunk ${c.index})\n${c.content}`,
    )
    .join("\n\n---\n\n");

  const userPrompt = `User question: ${question}
Question type: ${queryType}

Sources:
${sourcesBlock}
${
  revisionNotes
    ? `\nRevision notes from Critic (iteration ${iteration}):\n${revisionNotes}\nPlease rewrite the answer addressing these notes.`
    : ""
}

Now synthesize a grounded answer. Cite sources as [1], [2], etc.`;

  try {
    const rawAnswer = await chat(
      [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: userPrompt },
      ],
      { temperature: 0.3, maxTokens: 800 },
    );

    // Defensive check: if the LLM hallucinated a JSON structure (e.g. {"answer": "..."}), extract it
    const trimmed = rawAnswer.trim();
    if (trimmed.startsWith("{")) {
      try {
        const parsed = JSON.parse(trimmed.replace(/^```(?:json)?\s*\n?/i, "").replace(/\n?\s*```\s*$/i, ""));
        if (parsed && typeof parsed === "object") {
          answer = parsed.answer || parsed.text || parsed.content || rawAnswer;
        } else {
          answer = rawAnswer;
        }
      } catch {
        answer = rawAnswer; // Fallback to raw if unparseable
      }
    } else {
      answer = rawAnswer;
    }

    status = "completed";
  } catch (e: any) {
    console.error("[Analyzer Agent] Fatal error during synthesis:", e);
    answer =
      "I'm sorry, I encountered an error while synthesizing the answer. Please try again.";
    status = "error";
    error = e?.message ?? "Unknown analyzer error";
  }

  const finishedAt = Date.now();
  // Count distinct [n] citations actually used in the answer
  const citationsUsed = new Set(
    [...answer.matchAll(/\[(\d+)\]/g)].map((m) => m[1]),
  ).size;

  return {
    id: stepId,
    agent: "analyzer",
    label:
      iteration > 1
        ? `Rewriting answer (iteration ${iteration})`
        : "Synthesizing grounded answer",
    startedAt,
    finishedAt,
    durationMs: finishedAt - startedAt,
    status,
    error,
    input: { query: question, numSources: chunks.length, iteration },
    output: { answer, citationsUsed },
  };
}
