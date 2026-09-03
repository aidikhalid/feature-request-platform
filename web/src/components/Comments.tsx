import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useAddComment, useComments } from '../api/hooks';
import { ErrorState, InlineError, Skeleton } from './Feedback';
import { formatRelative } from '../lib/format';

export function CommentList({ requestId }: { requestId: number }) {
  const { data, isPending, isError, error, refetch } = useComments(requestId);

  if (isPending) return <Skeleton rows={2} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} />;
  if (data.length === 0) return <p className="subtle">No comments yet. Start the discussion.</p>;

  return (
    <div>
      {data.map((comment) => (
        <article className="comment" key={comment.id}>
          <div className="comment-head">
            <span className="comment-author">{comment.author.display_name}</span>
            <time className="subtle small" dateTime={comment.created_at}>
              {formatRelative(comment.created_at)}
            </time>
          </div>
          <p className="comment-body">{comment.body}</p>
        </article>
      ))}
    </div>
  );
}

interface FormProps {
  requestId: number;
  canComment: boolean;
  disabled?: boolean;
}

export function CommentForm({ requestId, canComment, disabled }: FormProps) {
  const [body, setBody] = useState('');
  const addComment = useAddComment(requestId);

  if (disabled) return null;

  if (!canComment) {
    return (
      <p className="notice notice-info">
        <Link to="/login">Sign in</Link> to join the discussion.
      </p>
    );
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    addComment.mutate(trimmed, { onSuccess: () => setBody('') });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="comment-body">Add a comment</label>
        <textarea
          id="comment-body"
          value={body}
          maxLength={2000}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Share why this matters to you"
        />
      </div>
      <InlineError error={addComment.error} />
      <button type="submit" className="btn btn-primary" disabled={!body.trim() || addComment.isPending}>
        {addComment.isPending ? 'Posting…' : 'Post comment'}
      </button>
    </form>
  );
}
