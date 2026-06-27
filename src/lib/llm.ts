/**
 * LLM wrapper around z-ai-web-dev-sdk.
 *
 * This module isolates the rest of the codebase from the SDK's specifics so
 * swapping providers (OpenAI / Anthropic / local) later is a one-file change.
 *
 * SERVER-ONLY. Do not import from client components.
 */

import "server-only";
import ZAI from "z-ai-web-dev-sdk";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmCallOptions {
  temperature?: number;
  maxTokens?: number;
  thinking?: "enabled" | "disabled";
}

let cachedClient: Awaited<ReturnType<typeof ZAI.create>> | null = null;

async function getClient() {
  if (cachedClient) return cachedClient;
  cachedClient = await ZAI.create();
  return cachedClient;
}

/**
 * Single-shot chat completion. Returns the assistant's textual reply.
 * Throws on error — callers are responsible for catching + logging.
 */
export async function chat(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
): Promise<string> {
  const client = await getClient();
  const completion = await client.chat.completions.create({
    messages: messages as any,
    temperature: options.temperature ?? 0.4,
    max_tokens: options.maxTokens ?? 800,
    thinking: { type: options.thinking === "enabled" ? "enabled" : "disabled" },
  } as any);
  const content = completion.choices?.[0]?.message?.content ?? "";
  return typeof content === "string" ? content : "";
}

/**
 * Ask the LLM to return a JSON object. We instruct the model to emit JSON only,
 * then defensively strip any markdown code fences. If parsing fails, the caller
 * can fall back to a default.
 */
export async function chatJson<T = unknown>(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
): Promise<T> {
  const raw = await chat(messages, {
    ...options,
    temperature: options.temperature ?? 0,
  });
  const cleaned = raw
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/i, "")
    .trim();
  return JSON.parse(cleaned) as T;
}
