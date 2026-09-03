import type { FeatureRequestDetail } from '../api/types';
import { formatDate } from '../lib/format';

/** The team's answer, deliberately styled apart from user comments. */
export function OfficialResponse({ request }: { request: FeatureRequestDetail }) {
  if (!request.official_response) return null;

  return (
    <section className="official" aria-labelledby="official-response-heading">
      <h3 id="official-response-heading">Official response</h3>
      <p className="comment-body">{request.official_response}</p>
      <p className="subtle small" style={{ margin: 0 }}>
        {request.official_response_by?.display_name ?? 'The team'}
        {request.official_response_at ? ` · ${formatDate(request.official_response_at)}` : ''}
      </p>
    </section>
  );
}
