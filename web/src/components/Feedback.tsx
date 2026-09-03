import type { ReactNode } from 'react';

import { ApiError } from '../api/client';

/**
 * The four states every data view needs. Collected here so no screen quietly forgets
 * one — a list that renders nothing while loading looks broken.
 */

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="stack" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="card" aria-hidden="true">
          <div className="skeleton" style={{ height: '1.1rem', width: '55%', marginBottom: '0.6rem' }} />
          <div className="skeleton" style={{ height: '0.8rem', width: '30%' }} />
        </div>
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : 'Something went wrong. Please try again.';
  return (
    <div className="notice notice-error" role="alert">
      <p style={{ margin: 0 }}>{message}</p>
      {onRetry && (
        <p style={{ margin: '0.6rem 0 0' }}>
          <button type="button" className="btn" onClick={onRetry}>
            Try again
          </button>
        </p>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty card">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

/** Announces mutation failures to screen readers as well as showing them. */
export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : 'Something went wrong.';
  return (
    <p className="field-error" role="alert" aria-live="assertive">
      {message}
    </p>
  );
}
