/**
 * Configuration System
 * Centralized, provider-agnostic configuration via environment variables.
 */

export type LlmProvider = "openrouter" | "ollama" | "openai" | "anthropic";

export const config = {
  llm: {
    provider: (process.env.LLM_PROVIDER as LlmProvider) || "openrouter",
    baseUrl: process.env.LLM_BASE_URL || "https://openrouter.ai/api/v1",
    model: process.env.LLM_MODEL || "google/gemini-2.5-flash",
    timeoutMs: parseInt(process.env.LLM_TIMEOUT || "30000", 10),
    maxRetries: parseInt(process.env.LLM_MAX_RETRIES || "3", 10),
    maxTokens: parseInt(process.env.LLM_MAX_TOKENS || "800", 10),
    temperature: parseFloat(process.env.LLM_TEMPERATURE || "0.4"),
    topP: parseFloat(process.env.LLM_TOP_P || "1.0"),
    stream: process.env.LLM_STREAM === "true",
    apiKey: (process.env.OPENROUTER_API_KEY || process.env.LLM_API_KEY || "").trim(),
  },
  vector: {
    provider: process.env.VECTOR_PROVIDER || "local_tfidf",
  },
  embedding: {
    provider: process.env.EMBEDDING_PROVIDER || "local_hash",
  },
  app: {
    uploadAccessKey: process.env.UPLOAD_ACCESS_KEY || "",
    databaseUrl: process.env.DATABASE_URL || "file:./db/custom.db",
    isDev: process.env.NODE_ENV === "development",
  }
};
