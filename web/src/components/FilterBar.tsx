import { useEffect, useId, useState } from 'react';

import { STATUS_LABELS, STATUSES, type ListParams, type RequestStatus, type SortOption } from '../api/types';

interface Props {
  value: ListParams;
  onChange: (next: Partial<ListParams>) => void;
}

const SORT_LABELS: Record<SortOption, string> = {
  top: 'Most voted',
  new: 'Newest',
  discussed: 'Most discussed',
};

/**
 * Search, filter and sort.
 *
 * The committed values live in the URL (see BrowsePage), not in this component — that
 * makes a filtered view shareable and the browser's back button work properly. Only the
 * in-progress text typed into the search box is local, and it is debounced so typing
 * does not fire a request per keystroke.
 */
export function FilterBar({ value, onChange }: Props) {
  const searchId = useId();
  const statusId = useId();
  const sortId = useId();
  const [draft, setDraft] = useState(value.q ?? '');

  // Keep the box in step when the URL changes from elsewhere (back button, a reset link).
  useEffect(() => {
    setDraft(value.q ?? '');
  }, [value.q]);

  useEffect(() => {
    if (draft === (value.q ?? '')) return;
    const timer = setTimeout(() => onChange({ q: draft, page: 1 }), 300);
    return () => clearTimeout(timer);
  }, [draft, value.q, onChange]);

  return (
    <form className="filters" role="search" onSubmit={(event) => event.preventDefault()}>
      <div>
        <label htmlFor={searchId}>Search</label>
        <input
          id={searchId}
          type="search"
          value={draft}
          placeholder="Search titles and descriptions"
          onChange={(event) => setDraft(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor={statusId}>Status</label>
        <select
          id={statusId}
          value={value.status ?? ''}
          onChange={(event) =>
            onChange({ status: (event.target.value || '') as RequestStatus | '', page: 1 })
          }
        >
          <option value="">All statuses</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor={sortId}>Sort by</label>
        <select
          id={sortId}
          value={value.sort ?? 'top'}
          onChange={(event) => onChange({ sort: event.target.value as SortOption, page: 1 })}
        >
          {(Object.keys(SORT_LABELS) as SortOption[]).map((sort) => (
            <option key={sort} value={sort}>
              {SORT_LABELS[sort]}
            </option>
          ))}
        </select>
      </div>
    </form>
  );
}
