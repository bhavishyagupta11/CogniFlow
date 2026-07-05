/**
 * Error Architecture
 * Proper hierarchy for application errors.
 */

export type ErrorSeverity = "low" | "medium" | "high" | "critical";

export interface ErrorContext {
  provider?: string;
  agent?: string;
  requestId?: string;
  traceId?: string;
  retryable?: boolean;
  [key: string]: any;
}

export class BaseApplicationError extends Error {
  public code: string;
  public type: string;
  public severity: ErrorSeverity;
  public retryable: boolean;
  public provider?: string;
  public agent?: string;
  public requestId?: string;
  public traceId?: string;
  public timestamp: string;
  public cause?: any;
  public userMessage: string;
  public developerMessage: string;

  constructor(
    type: string,
    code: string,
    userMessage: string,
    developerMessage: string,
    severity: ErrorSeverity,
    context: ErrorContext = {},
    cause?: any
  ) {
    super(developerMessage);
    this.name = this.constructor.name;
    this.type = type;
    this.code = code;
    this.severity = severity;
    this.retryable = context.retryable ?? false;
    this.provider = context.provider;
    this.agent = context.agent;
    this.requestId = context.requestId;
    this.traceId = context.traceId;
    this.timestamp = new Date().toISOString();
    this.cause = cause;
    this.userMessage = userMessage;
    this.developerMessage = developerMessage;

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  toJSON() {
    return {
      name: this.name,
      type: this.type,
      code: this.code,
      severity: this.severity,
      retryable: this.retryable,
      provider: this.provider,
      agent: this.agent,
      requestId: this.requestId,
      traceId: this.traceId,
      timestamp: this.timestamp,
      userMessage: this.userMessage,
      developerMessage: this.developerMessage,
      cause: this.cause ? String(this.cause) : undefined,
      stack: this.stack
    };
  }
}

export class InfrastructureError extends BaseApplicationError {
  constructor(code: string, userMsg: string, devMsg: string, context: ErrorContext = {}, cause?: any) {
    super("InfrastructureError", code, userMsg, devMsg, "critical", context, cause);
  }
}

export class ProviderError extends InfrastructureError {
  constructor(code: string, devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      code,
      "The AI provider is currently experiencing issues. Please try again later.",
      devMsg,
      context,
      cause
    );
  }
}

export class BillingError extends ProviderError {
  constructor(devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "BILLING_402",
      devMsg,
      { ...context, retryable: false },
      cause
    );
    this.userMessage = "The AI service is unavailable due to an account billing issue.";
  }
}

export class RateLimitError extends ProviderError {
  constructor(devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "RATE_LIMIT_429",
      devMsg,
      { ...context, retryable: true },
      cause
    );
    this.userMessage = "The AI service is currently too busy. Retrying...";
  }
}

export class AuthenticationError extends ProviderError {
  constructor(devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "AUTH_401",
      devMsg,
      { ...context, retryable: false },
      cause
    );
    this.userMessage = "The AI service is unavailable due to an authentication error.";
  }
}

export class ParsingError extends BaseApplicationError {
  constructor(code: string, devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "ParsingError",
      code,
      "An error occurred while interpreting the AI response.",
      devMsg,
      "high",
      { ...context, retryable: false },
      cause
    );
  }
}

export class RetrieverError extends BaseApplicationError {
  constructor(code: string, devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "RetrieverError",
      code,
      "Failed to search the knowledge base.",
      devMsg,
      "high",
      { ...context, retryable: false },
      cause
    );
  }
}

export class ValidationError extends BaseApplicationError {
  constructor(code: string, devMsg: string, context: ErrorContext = {}, cause?: any) {
    super(
      "ValidationError",
      code,
      "The query could not be validated.",
      devMsg,
      "medium",
      { ...context, retryable: false },
      cause
    );
  }
}
