import { useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';

import { useMe, useRequests } from '../api/hooks';
import type { ListParams, RequestStatus, SortOption } from '../api/types';
import { FilterBar } from '../components/FilterBar';
import { EmptyState, ErrorState, Skeleton } from '../components/Feedback';
import { RequestCard } from '../components/RequestCard';

/**
 * The board.
 *
 * Filter state is held in the URL rather than in component state, so a filtered view can
 * be shared or bookmarked and the back button behaves as users expect. The URL is the
 * single source of truth; React Query keys off it and caches each combination.
 */
export function BrowsePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { data: me } = useMe();

  const params: ListParams = {
    q: searchParams.get('q') ?? '',
    status: (searchParams.get('status') ?? '') as RequestStatus | '',
    sort: (searchParams.get('sort') ?? 'top') as SortOption,
    page: Number(searchParams.get('page') ?? 1),
  };

  const updateParams = useCallback(
    (next: Partial<ListParams>) => {
      setSearchParams(
        (current) => {
          const updated = new URLSearchParams(current);
          for (const [key, value] of Object.entries(next)) {
            if (value === undefined || value === '' || value === null) updated.delete(key);
            else updated.set(key, String(value));
          }
          // Defaults are omitted so the common URL stays clean.
          if (updated.get('page') === '1') updated.delete('page');
          if (updated.get('sort') === 'top') updated.delete('sort');
          return updated;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const { data, isPending, isError, error, refetch, isPlaceholderData } = useRequests(params);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Feature requests</h1>
          <p className="subtle">Vote for what matters to you, or suggest something new.</p>
        </div>
        <Link className="btn btn-primary" to="/requests/new">
          Submit a request
        </Link>
      </div>

      <FilterBar value={params} onChange={updateParams} />

      {isPending ? (
        <Skeleton rows={4} />
      ) : isError ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : data.items.length === 0 ? (
        <EmptyState title="Nothing matches those filters">
          <p>Try a different search term, or clear the filters to see everything.</p>
          <button
            type="button"
            className="btn"
            onClick={() => updateParams({ q: '', status: '', sort: 'top', page: 1 })}
          >
            Clear filters
          </button>
        </EmptyState>
      ) : (
        <>
          <p className="subtle small" aria-live="polite">
            {data.total} {data.total === 1 ? 'request' : 'requests'}
          </p>
          <div className="stack" style={{ opacity: isPlaceholderData ? 0.6 : 1 }}>
            {data.items.map((request) => (
              <RequestCard
                key={request.id}
                request={request}
                canVote={Boolean(me)}
                onRequireSignIn={() => navigate('/login')}
              />
            ))}
          </div>

          {data.total_pages > 1 && (
            <nav className="pagination" aria-label="Pagination">
              <button
                type="button"
                className="btn"
                disabled={data.page <= 1}
                onClick={() => updateParams({ page: data.page - 1 })}
              >
                Previous
              </button>
              <span className="subtle small">
                Page {data.page} of {data.total_pages}
              </span>
              <button
                type="button"
                className="btn"
                disabled={data.page >= data.total_pages}
                onClick={() => updateParams({ page: data.page + 1 })}
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </>
  );
}
