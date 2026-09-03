import { Link } from 'react-router-dom';

import type { FeatureRequestSummary } from '../api/types';
import { StatusBadge } from './StatusBadge';
import { VoteButton } from './VoteButton';
import { formatRelative } from '../lib/format';

interface Props {
  request: FeatureRequestSummary;
  canVote: boolean;
  onRequireSignIn: () => void;
}

export function RequestCard({ request, canVote, onRequireSignIn }: Props) {
  return (
    <article className="card request-card">
      <VoteButton request={request} canVote={canVote} onRequireSignIn={onRequireSignIn} />
      <div>
        <h3>
          <Link to={`/requests/${request.id}`}>{request.title}</Link>
        </h3>
        <div className="card-meta">
          <StatusBadge status={request.status} />
          <span>{request.author.display_name}</span>
          <span aria-hidden="true">·</span>
          <span>{formatRelative(request.created_at)}</span>
          <span aria-hidden="true">·</span>
          <span>
            {request.comment_count} {request.comment_count === 1 ? 'comment' : 'comments'}
          </span>
        </div>
      </div>
    </article>
  );
}
