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
import { RouterStep, RouterOutputSchema, RouterOutput } from "./types";
import { Result, success, failure } from "../result";
import { logger } from "../logger";
import { ParsingError, ValidationError, BaseApplicationError } from "../errors";

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
  requestId: string
): Promise<Result<RouterStep>> {
  const startedAt = Date.now();
  logger.info("Starting Router Agent", { requestId, agent: "router", stepId });

  if (!question || question.trim().length === 0) {
    return failure(
      new ValidationError("EMPTY_QUESTION", "The question cannot be empty.", { requestId, agent: "router" })
    );
  }

  try {
    const rawOutput = await chatJson<unknown>(
      [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: question },
      ],
      { temperature: 0, maxTokens: 300 },
      requestId,
      "router"
    );

    // Runtime validation using Zod
    const parseResult = RouterOutputSchema.safeParse(rawOutput);
    
    if (!parseResult.success) {
      const errorMsg = parseResult.error.errors.map(e => `${e.path.join(".")}: ${e.message}`).join(", ");
      logger.warn("Router validation failed, using fallback", { requestId, agent: "router", errors: errorMsg });
      throw new ParsingError("ROUTER_SCHEMA_MISMATCH", `Router output violated schema: ${errorMsg}`, { requestId, agent: "router" });
    }

    const output = parseResult.data;
    const finishedAt = Date.now();
    
    logger.info("Router Agent completed successfully", { 
      requestId, agent: "router", durationMs: finishedAt - startedAt, queryType: output.queryType 
    });

    return success({
      id: stepId,
      agent: "router",
      label: "Analyzing question & rewriting query",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "completed",
      input: { question },
      output,
    });
  } catch (e: any) {
    // If it's already an application error (e.g., InfrastructureError from chatJson), pass it up
    if (e instanceof BaseApplicationError) {
      return failure(e);
    }
    
    // Otherwise wrap it in a ParsingError
    return failure(
      new ParsingError("ROUTER_UNEXPECTED_ERROR", e?.message ?? "Unknown router error", { requestId, agent: "router" }, e)
    );
  }
}
