import { Link } from 'react-router-dom';

import { useMe, useStats } from '../api/hooks';
import { STATUS_LABELS, STATUSES } from '../api/types';
import { EmptyState, ErrorState, Skeleton } from '../components/Feedback';

/**
 * A small set of usage statistics — deliberately five numbers and two lists rather than
 * a charting library, which would be weight for very little insight at this scale.
 */
export function AdminPage() {
  const { data: me, isPending: meLoading } = useMe();
  const isAdmin = me?.role === 'admin';
  const { data, isPending, isError, error, refetch } = useStats(isAdmin);

  if (meLoading) return <Skeleton rows={2} />;

  if (!isAdmin) {
    // The API enforces this too — a standard user calling /api/admin/stats gets a 403.
    return (
      <EmptyState title="Administrators only">
        <p className="subtle">This page is only available to administrator accounts.</p>
        <Link className="btn" to="/">
          Back to requests
        </Link>
      </EmptyState>
    );
  }

  if (isPending) return <Skeleton rows={2} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} />;

  const maxByStatus = Math.max(1, ...STATUSES.map((status) => data.by_status[status] ?? 0));

  return (
    <div className="stack">
      <div>
        <h1>Usage statistics</h1>
        <p className="subtle">Merged duplicates are excluded from these totals.</p>
      </div>

      <div className="stat-grid">
        <Stat label="Open requests" value={data.total_requests} />
        <Stat label="Total votes" value={data.total_votes} />
        <Stat label="Total comments" value={data.total_comments} />
        <Stat label="New this week" value={data.requests_last_7_days} />
      </div>

      <section className="card" aria-labelledby="by-status-heading">
        <h2 id="by-status-heading">Requests by status</h2>
        {STATUSES.map((status) => {
          const count = data.by_status[status] ?? 0;
          return (
            <div className="bar-row" key={status}>
              <span className="bar-label">{STATUS_LABELS[status]}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(count / maxByStatus) * 100}%` }} />
              </div>
              <span className="small" style={{ width: '2rem', textAlign: 'right' }}>
                {count}
              </span>
            </div>
          );
        })}
      </section>

      <section className="card" aria-labelledby="top-heading">
        <h2 id="top-heading">Most requested</h2>
        {data.top_requests.length === 0 ? (
          <p className="subtle">No requests yet.</p>
        ) : (
          <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
            {data.top_requests.map((request) => (
              <li key={request.id} style={{ marginBottom: '0.3rem' }}>
                <Link to={`/requests/${request.id}`}>{request.title}</Link>{' '}
                <span className="subtle small">
                  — {request.vote_count} {request.vote_count === 1 ? 'vote' : 'votes'}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
