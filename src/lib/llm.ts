/**
 * Enterprise LLM wrapper with centralized configuration, structured logging,
 * intelligent retries, and structured error propagation.
 *
 * SERVER-ONLY. Do not import from client components.
 */

import "server-only";
import OpenAI from "openai";
import { config } from "./config";
import { logger } from "./logger";
import { BillingError, RateLimitError, ProviderError, AuthenticationError, ParsingError } from "./errors";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmCallOptions {
  temperature?: number;
  maxTokens?: number;
  topP?: number;
}

let cachedClient: OpenAI | null = null;

function getClient(): OpenAI {
  if (cachedClient) return cachedClient;
  
  const apiKey = config.llm.apiKey;
  if (!apiKey) {
    throw new ProviderError("NO_API_KEY", "LLM API key is not configured.");
  }
  
  cachedClient = new OpenAI({
    baseURL: config.llm.baseUrl,
    apiKey: apiKey,
    defaultHeaders: {
      "HTTP-Referer": "https://cogniflow.local",
      "X-Title": "CogniFlow Enterprise RAG",
    }
  });
  
  return cachedClient;
}

export async function chat(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
  retries = config.llm.maxRetries,
  requestId: string = "unknown-request",
  agent: string = "system"
): Promise<string> {
  const client = getClient();
  const startTime = Date.now();
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      logger.debug("Dispatching LLM chat request", { 
        requestId, agent, attempt, model: config.llm.model 
      });

      const completion = await client.chat.completions.create({
        model: config.llm.model,
        messages: messages,
        temperature: options.temperature ?? config.llm.temperature,
        max_tokens: options.maxTokens ?? config.llm.maxTokens,
        top_p: options.topP ?? config.llm.topP,
      });

      const durationMs = Date.now() - startTime;
      logger.info("LLM chat request succeeded", { 
        requestId, agent, attempt, durationMs, model: config.llm.model 
      });

      return completion.choices[0]?.message?.content ?? "";
    } catch (e: any) {
      const status = e?.status || (e.response && e.response.status) || 500;
      const errorMsg = e?.message ?? String(e);
      const durationMs = Date.now() - startTime;
      
      logger.warn("LLM chat request failed", { 
        requestId, agent, attempt, status, error: errorMsg, durationMs 
      });

      // Intelligent Retry Logic
      const isRetryable = status === 429 || (status >= 500 && status <= 504);
      
      if (isRetryable && attempt < retries) {
        const delay = Math.pow(2, attempt) * 1000;
        logger.info(`Retrying LLM request in ${delay}ms...`, { requestId, agent, attempt });
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      
      // Map to structured errors if retries exhausted or non-retryable
      const context = { provider: config.llm.provider, agent, requestId };
      
      if (status === 402) throw new BillingError(errorMsg, context, e);
      if (status === 429) throw new RateLimitError(errorMsg, context, e);
      if (status === 401 || status === 403) throw new AuthenticationError(errorMsg, context, e);
      
      throw new ProviderError("LLM_CALL_FAILED", errorMsg, context, e);
    }
  }
  
  throw new ProviderError("MAX_RETRIES_EXCEEDED", "Exhausted all retries.", { agent, requestId, provider: config.llm.provider });
}

export async function chatJson<T = unknown>(
  messages: ChatMessage[],
  options: LlmCallOptions = {},
  requestId: string = "unknown-request",
  agent: string = "system"
): Promise<T> {
  const raw = await chat(messages, {
    ...options,
    temperature: options.temperature ?? 0,
  }, config.llm.maxRetries, requestId, agent);

  let cleaned = raw.trim();
  cleaned = cleaned.replace(/^```(?:json)?\s*\n?/i, "");
  cleaned = cleaned.replace(/\n?\s*```\s*$/i, "");
  cleaned = cleaned.trim();

  try {
    return JSON.parse(cleaned) as T;
  } catch (parseErr: any) {
    logger.warn("JSON parse failed on first pass, attempting regex fallback", { requestId, agent, rawSnippet: raw.substring(0, 100) });
    
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      try {
        return JSON.parse(jsonMatch[0]) as T;
      } catch (fallbackErr) {
        logger.error("Regex fallback JSON parse also failed", fallbackErr, { requestId, agent });
      }
    }
    
    throw new ParsingError("JSON_PARSE_FAILED", `Failed to parse LLM response: ${parseErr?.message}`, { requestId, agent, provider: config.llm.provider }, parseErr);
  }
}
