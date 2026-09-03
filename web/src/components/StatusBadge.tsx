import { STATUS_LABELS, type RequestStatus } from '../api/types';

/** Status shown as both colour and text — colour alone would exclude some readers. */
export function StatusBadge({ status }: { status: RequestStatus }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABELS[status]}</span>;
}
