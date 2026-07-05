/**
 * Token Estimator Interface
 *
 * Provides a pluggable architecture for estimating tokens.
 * Currently uses an approximate heuristic, but designed to be swapped
 * with exact tokenizers (like tiktoken) when needed.
 */

import { logger } from "../logger";

export interface TokenEstimator {
  estimateTokens(text: string): number;
  providerName: string;
}

export class ApproximateTokenEstimator implements TokenEstimator {
  providerName = "heuristic_approximate";

  estimateTokens(text: string): number {
    if (!text) return 0;
    // 1 token ~= 4 characters in English
    const estimated = Math.ceil(text.length / 4);
    
    logger.trace("Token estimation (approximate)", { 
      chars: text.length, 
      estimatedTokens: estimated 
    });
    
    return estimated;
  }
}

// Global default estimator
export const tokenEstimator: TokenEstimator = new ApproximateTokenEstimator();
