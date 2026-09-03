import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { FilterBar } from './FilterBar';

describe('FilterBar', () => {
  it('reports status and sort changes immediately, resetting to page one', async () => {
    const onChange = vi.fn();
    render(<FilterBar value={{ q: '', status: '', sort: 'top', page: 3 }} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'planned');
    expect(onChange).toHaveBeenCalledWith({ status: 'planned', page: 1 });

    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'new');
    expect(onChange).toHaveBeenCalledWith({ sort: 'new', page: 1 });
  });

  it('debounces typing so a search is not fired per keystroke', async () => {
    const onChange = vi.fn();
    render(<FilterBar value={{ q: '', status: '', sort: 'top', page: 1 }} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText('Search'), 'dark');

    // Four keystrokes, and none of them has committed yet.
    expect(onChange).not.toHaveBeenCalled();

    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ q: 'dark', page: 1 }));
    expect(onChange).toHaveBeenCalledOnce();
  });

  it('shows the committed filter values it is given', () => {
    render(
      <FilterBar value={{ q: 'export', status: 'released', sort: 'discussed', page: 1 }} onChange={vi.fn()} />,
    );

    expect(screen.getByLabelText('Search')).toHaveValue('export');
    expect(screen.getByLabelText('Status')).toHaveValue('released');
    expect(screen.getByLabelText('Sort by')).toHaveValue('discussed');
  });
});
