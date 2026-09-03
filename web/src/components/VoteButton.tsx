import { useToggleVote } from '../api/hooks';
import type { FeatureRequestSummary } from '../api/types';

interface Props {
  request: Pick<FeatureRequestSummary, 'id' | 'title' | 'vote_count' | 'has_voted' | 'merged_into_id'>;
  /** Signed out visitors see the count but cannot vote. */
  canVote: boolean;
  onRequireSignIn?: () => void;
}

/**
 * A toggle, not two buttons.
 *
 * `aria-pressed` is what tells assistive technology whether the vote is cast; the colour
 * change alone would not. The count updates optimistically (see useToggleVote), and the
 * label always describes the action the click will perform.
 */
export function VoteButton({ request, canVote, onRequireSignIn }: Props) {
  const toggle = useToggleVote(request);
  const disabled = request.merged_into_id !== null;

  const handleClick = () => {
    if (!canVote) {
      onRequireSignIn?.();
      return;
    }
    toggle.mutate(!request.has_voted);
  };

  return (
    <button
      type="button"
      className="vote"
      aria-pressed={request.has_voted}
      aria-label={`${request.has_voted ? 'Remove your vote from' : 'Vote for'} “${request.title}”. ${request.vote_count} ${request.vote_count === 1 ? 'vote' : 'votes'}.`}
      onClick={handleClick}
      disabled={disabled}
      title={disabled ? 'This request was merged into another one' : undefined}
    >
      <span className="caret" aria-hidden="true">
        ▲
      </span>
      <span className="count">{request.vote_count}</span>
      <span className="label" aria-hidden="true">
        {request.has_voted ? 'Voted' : 'Vote'}
      </span>
    </button>
  );
}
