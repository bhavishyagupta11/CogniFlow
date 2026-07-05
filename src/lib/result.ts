/**
 * Unified Result Contract
 * Single internal Result type for all services to return.
 */

import { BaseApplicationError } from "./errors";

export type Result<T, E extends BaseApplicationError = BaseApplicationError> = 
  | { success: true; data: T; error?: never }
  | { success: false; data?: never; error: E };

export function success<T>(data: T): Result<T, any> {
  return { success: true, data };
}

export function failure<E extends BaseApplicationError>(error: E): Result<any, E> {
  return { success: false, error };
}

/**
 * Helper to unwrap a result, throwing the error if it failed.
 * Use cautiously, ideally only at the edges of the application.
 */
export function unwrap<T, E extends BaseApplicationError>(result: Result<T, E>): T {
  if (!result.success) {
    throw result.error;
  }
  return result.data;
}
