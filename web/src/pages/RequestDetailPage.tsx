import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useMe, useRequest, useUpdateRequest } from '../api/hooks';
import { AdminControls } from '../components/AdminControls';
import { CommentForm, CommentList } from '../components/Comments';
import { EmptyState, ErrorState, InlineError, Skeleton } from '../components/Feedback';
import { OfficialResponse } from '../components/OfficialResponse';
import { StatusBadge } from '../components/StatusBadge';
import { VoteButton } from '../components/VoteButton';
import { formatRelative } from '../lib/format';

export function RequestDetailPage() {
  const { id } = useParams();
  const requestId = Number(id);
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: request, isPending, isError, error, refetch } = useRequest(requestId);
  const [editing, setEditing] = useState(false);

  if (Number.isNaN(requestId)) return <EmptyState title="That request does not exist" />;
  if (isPending) return <Skeleton rows={3} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} />;

  const isOwner = me?.id === request.author.id;
  const isAdmin = me?.role === 'admin';
  const isMerged = request.merged_into_id !== null;

  return (
    <div className="stack">
      <p className="small">
        <Link to="/">← Back to all requests</Link>
      </p>

      {isMerged && (
        <p className="notice notice-info" role="status">
          This request was merged into{' '}
          <Link to={`/requests/${request.merged_into_id}`}>another request</Link>. Its votes and
          comments moved there.
        </p>
      )}

      <article className="card">
        <div className="request-card">
          <VoteButton
            request={request}
            canVote={Boolean(me)}
            onRequireSignIn={() => navigate('/login')}
          />
          <div style={{ flex: 1 }}>
            {editing ? (
              <EditForm requestId={requestId} request={request} onDone={() => setEditing(false)} />
            ) : (
              <>
                <h1>{request.title}</h1>
                <div className="card-meta" style={{ marginBottom: '0.9rem' }}>
                  <StatusBadge status={request.status} />
                  <span>{request.author.display_name}</span>
                  <span aria-hidden="true">·</span>
                  <time dateTime={request.created_at}>{formatRelative(request.created_at)}</time>
                  {(isOwner || isAdmin) && !isMerged && (
                    <>
                      <span aria-hidden="true">·</span>
                      <button type="button" className="btn-link" onClick={() => setEditing(true)}>
                        Edit
                      </button>
                    </>
                  )}
                </div>
                <p className="comment-body">{request.description}</p>
              </>
            )}
          </div>
        </div>
      </article>

      <OfficialResponse request={request} />

      {isAdmin && <AdminControls request={request} />}

      <section className="card stack" aria-labelledby="comments-heading">
        <h2 id="comments-heading">
          {request.comment_count} {request.comment_count === 1 ? 'comment' : 'comments'}
        </h2>
        <CommentList requestId={requestId} />
        <CommentForm requestId={requestId} canComment={Boolean(me)} disabled={isMerged} />
      </section>
    </div>
  );
}

function EditForm({
  requestId,
  request,
  onDone,
}: {
  requestId: number;
  request: { title: string; description: string };
  onDone: () => void;
}) {
  const update = useUpdateRequest(requestId);
  const [title, setTitle] = useState(request.title);
  const [description, setDescription] = useState(request.description);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    update.mutate({ title, description }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="edit-title">Title</label>
        <input id="edit-title" value={title} onChange={(event) => setTitle(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="edit-description">Description</label>
        <textarea
          id="edit-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      <InlineError error={update.error} />
      <div className="admin-row">
        <button type="submit" className="btn btn-primary" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save changes'}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}
