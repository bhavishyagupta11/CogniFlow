/**
 * LLM wrapper using OpenRouter (via OpenAI SDK).
 *
 * This module isolates the rest of the codebase from the SDK's specifics so
 * swapping providers (OpenAI / Anthropic / local) later is a one-file change.
 *
 * SERVER-ONLY. Do not import from client components.
 */

import "server-only";
import OpenAI from "openai";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmCallOptions {
  temperature?: number;
  maxTokens?: number;
  thinking?: "enabled" | "disabled";
}

let cachedClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (cachedClient) return cachedClient;
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error("OPENROUTER_API_KEY is not set in .env");
  }
  
  cachedClient = new OpenAI({
    baseURL: "https://openrouter.ai/api/v1",
    apiKey: apiKey,
    defaultHeaders: {
      "HTTP-Referer": "http://localhost:3000",
      "X-Title": "CogniFlow MultiAgent RAG",
    }
  });
  
  return cachedClient;
}

export async function chat(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
  retries = 1,
): Promise<string> {
  const client = getClient();
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const completion = await client.chat.completions.create({
        model: "google/gemini-2.5-flash", // Extremely fast and reliable via OpenRouter
        messages: messages,
        temperature: options.temperature ?? 0.4,
        max_tokens: options.maxTokens ?? 800,
      });

      return completion.choices[0]?.message?.content ?? "";
    } catch (e: any) {
      if (attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        continue;
      }
      console.error("[LLM] OpenRouter chat error:", e?.message ?? e);
      throw e;
    }
  }
  throw new Error("Max retries exceeded");
}

export async function chatJson<T = unknown>(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
): Promise<T> {
  const raw = await chat(messages, {
    ...options,
    temperature: options.temperature ?? 0,
  });

  let cleaned = raw.trim();
  cleaned = cleaned.replace(/^```(?:json)?\s*\n?/i, "");
  cleaned = cleaned.replace(/\n?\s*```\s*$/i, "");
  cleaned = cleaned.trim();

  try {
    return JSON.parse(cleaned) as T;
  } catch (parseErr: any) {
    console.error("[LLM] JSON parse failed. Raw response:", raw);
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        return JSON.parse(jsonMatch[0]) as T;
      } catch {
        // Give up
      }
    }
    throw new Error(`Failed to parse LLM JSON response: ${parseErr?.message}`);
  }
}
