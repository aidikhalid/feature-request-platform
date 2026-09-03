import { useEffect, useState } from 'react';

import { useMergeRequest, useRequests, useSetOfficialResponse, useSetStatus } from '../api/hooks';
import { STATUS_LABELS, STATUSES, type FeatureRequestDetail, type RequestStatus } from '../api/types';
import { InlineError } from './Feedback';

/**
 * Admin actions for a single request. Rendered only for administrators — but note that
 * this is a convenience, not a security boundary: the API rejects these calls from a
 * standard user regardless of what the UI shows.
 */
export function AdminControls({ request }: { request: FeatureRequestDetail }) {
  return (
    <section className="card admin-panel stack" aria-labelledby="admin-heading">
      <h2 id="admin-heading">Admin</h2>
      <StatusControl request={request} />
      <ResponseControl request={request} />
      <MergeControl request={request} />
    </section>
  );
}

function StatusControl({ request }: { request: FeatureRequestDetail }) {
  const setStatus = useSetStatus(request.id);
  const [status, setStatus_] = useState<RequestStatus>(request.status);

  useEffect(() => setStatus_(request.status), [request.status]);

  return (
    <div>
      <div className="admin-row">
        <div className="field">
          <label htmlFor="admin-status">Status</label>
          <select
            id="admin-status"
            value={status}
            onChange={(event) => setStatus_(event.target.value as RequestStatus)}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={status === request.status || setStatus.isPending}
          onClick={() => setStatus.mutate(status)}
        >
          {setStatus.isPending ? 'Saving…' : 'Update status'}
        </button>
      </div>
      <InlineError error={setStatus.error} />
      <p aria-live="polite" className="sr-only">
        {setStatus.isSuccess ? `Status updated to ${STATUS_LABELS[request.status]}` : ''}
      </p>
    </div>
  );
}

function ResponseControl({ request }: { request: FeatureRequestDetail }) {
  const setResponse = useSetOfficialResponse(request.id);
  const [body, setBody] = useState(request.official_response ?? '');

  useEffect(() => setBody(request.official_response ?? ''), [request.official_response]);

  return (
    <div>
      <div className="field">
        <label htmlFor="admin-response">Official response</label>
        <textarea
          id="admin-response"
          value={body}
          maxLength={5000}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Explain the decision or the timeline"
        />
      </div>
      <InlineError error={setResponse.error} />
      <button
        type="button"
        className="btn btn-primary"
        disabled={!body.trim() || body === (request.official_response ?? '') || setResponse.isPending}
        onClick={() => setResponse.mutate(body)}
      >
        {setResponse.isPending ? 'Saving…' : 'Publish response'}
      </button>
    </div>
  );
}

/**
 * Merge this request into another one.
 *
 * The confirmation text is explicit about the direction and the consequence, because the
 * action moves other people's votes and comments and cannot be undone through the UI.
 */
function MergeControl({ request }: { request: FeatureRequestDetail }) {
  const merge = useMergeRequest(request.id);
  const [targetId, setTargetId] = useState('');
  const [confirming, setConfirming] = useState(false);

  // A short list of candidates to merge into, newest first, excluding this request.
  const { data } = useRequests({ sort: 'new', page: 1 });
  const candidates = (data?.items ?? []).filter((item) => item.id !== request.id);
  const target = candidates.find((item) => String(item.id) === targetId);

  if (request.merged_into_id !== null) {
    return <p className="subtle small">This request has already been merged.</p>;
  }

  return (
    <div>
      <div className="admin-row">
        <div className="field">
          <label htmlFor="admin-merge">Merge this request into</label>
          <select
            id="admin-merge"
            value={targetId}
            onChange={(event) => {
              setTargetId(event.target.value);
              setConfirming(false);
            }}
          >
            <option value="">Choose the surviving request…</option>
            {candidates.map((item) => (
              <option key={item.id} value={item.id}>
                #{item.id} — {item.title}
              </option>
            ))}
          </select>
        </div>
        {!confirming ? (
          <button
            type="button"
            className="btn"
            disabled={!target}
            onClick={() => setConfirming(true)}
          >
            Merge…
          </button>
        ) : (
          <>
            <button
              type="button"
              className="btn btn-primary"
              disabled={merge.isPending}
              onClick={() => merge.mutate(Number(targetId))}
            >
              {merge.isPending ? 'Merging…' : 'Confirm merge'}
            </button>
            <button type="button" className="btn" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </>
        )}
      </div>
      {confirming && target && (
        <p className="notice notice-info small" role="alert">
          “{request.title}” will be closed as a duplicate. Its {request.vote_count} vote
          {request.vote_count === 1 ? '' : 's'} and {request.comment_count} comment
          {request.comment_count === 1 ? '' : 's'} move to “{target.title}”. Anyone who voted for
          both will still be counted once. This cannot be undone here.
        </p>
      )}
      <InlineError error={merge.error} />
    </div>
  );
}
