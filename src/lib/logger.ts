/**
 * Structured Enterprise Logger
 * Emits machine-readable JSON logs.
 */

export type LogLevel = "TRACE" | "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL";

export interface LogContext {
  requestId?: string;
  traceId?: string;
  sessionId?: string;
  agent?: string;
  node?: string;
  provider?: string;
  model?: string;
  durationMs?: number;
  memoryMb?: number;
  cpuPercent?: number;
  threadId?: string;
  retryCount?: number;
  [key: string]: any;
}

export class Logger {
  private baseContext: LogContext = {};

  constructor(baseContext: LogContext = {}) {
    this.baseContext = baseContext;
  }

  child(context: LogContext): Logger {
    return new Logger({ ...this.baseContext, ...context });
  }

  private emit(level: LogLevel, message: string, ctx?: LogContext, error?: any) {
    const memUsage = process.memoryUsage();
    
    const payload = {
      timestamp: new Date().toISOString(),
      severity: level,
      message,
      ...this.baseContext,
      ...ctx,
      memory: {
        rss: Math.round(memUsage.rss / 1024 / 1024),
        heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024),
      },
      error: error ? {
        message: error.message,
        stack: error.stack,
        code: error.code,
      } : undefined
    };

    const out = JSON.stringify(payload);
    
    if (level === "ERROR" || level === "FATAL") {
      console.error(out);
    } else if (level === "WARN") {
      console.warn(out);
    } else {
      console.log(out);
    }
  }

  trace(msg: string, ctx?: LogContext) { this.emit("TRACE", msg, ctx); }
  debug(msg: string, ctx?: LogContext) { this.emit("DEBUG", msg, ctx); }
  info(msg: string, ctx?: LogContext) { this.emit("INFO", msg, ctx); }
  warn(msg: string, ctx?: LogContext, err?: any) { this.emit("WARN", msg, ctx, err); }
  error(msg: string, err: any, ctx?: LogContext) { this.emit("ERROR", msg, ctx, err); }
  fatal(msg: string, err: any, ctx?: LogContext) { this.emit("FATAL", msg, ctx, err); }
}

export const logger = new Logger();
