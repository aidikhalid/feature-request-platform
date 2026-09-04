import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import type { FeatureRequestSummary, Page, User } from './api/types';

/**
 * A smoke test for the whole shell: routing, the header's auth state, and the board.
 *
 * The component tests cover behaviour in isolation; this one exists to catch the wiring
 * mistakes they cannot see — a bad import, a missing provider, a route that throws on
 * render.
 */

const REQUEST: FeatureRequestSummary = {
  id: 1,
  title: 'Dark mode across the whole app',
  status: 'planned',
  vote_count: 12,
  comment_count: 3,
  created_at: new Date().toISOString(),
  author: { id: 5, display_name: 'Shinji Ikari' },
  merged_into_id: null,
  has_voted: false,
};

const BOARD: Page<FeatureRequestSummary> = {
  items: [REQUEST],
  page: 1,
  page_size: 20,
  total: 1,
  total_pages: 1,
};

const ADMIN: User = {
  id: 1,
  email: 'admin@example.com',
  display_name: 'Gendo Admin',
  role: 'admin',
  created_at: new Date().toISOString(),
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** Routes fetch calls by path so each test only states what it cares about. */
function stubApi(routes: Record<string, () => Response>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const path = new URL(url).pathname;
      const handler = routes[path];
      if (!handler) throw new Error(`unexpected request to ${path}`);
      return Promise.resolve(handler());
    }),
  );
}

function renderApp(route = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App', () => {
  it('shows the board and invites a signed-out visitor to sign in', async () => {
    stubApi({
      '/api/auth/me': () => json({ error: { code: 'unauthorized', message: 'Authentication required' } }, 401),
      '/api/requests': () => json(BOARD),
    });

    renderApp();

    expect(await screen.findByRole('heading', { level: 1, name: 'Feature requests' })).toBeInTheDocument();
    expect(await screen.findByText('Dark mode across the whole app')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument();
    // The statistics link is for administrators only.
    expect(screen.queryByRole('link', { name: 'Statistics' })).not.toBeInTheDocument();
  });

  it('greets a signed-in administrator and offers the statistics page', async () => {
    stubApi({
      '/api/auth/me': () => json(ADMIN),
      '/api/requests': () => json(BOARD),
    });

    renderApp();

    expect(await screen.findByText(/Gendo Admin/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Statistics' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
  });

  it('renders an empty state rather than a blank screen when nothing matches', async () => {
    stubApi({
      '/api/auth/me': () => json(null),
      '/api/requests': () => json({ ...BOARD, items: [], total: 0, total_pages: 1 }),
    });

    renderApp();

    expect(await screen.findByText('Nothing matches those filters')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument();
  });

  it('surfaces a failed board load with a retry', async () => {
    stubApi({
      '/api/auth/me': () => json(null),
      '/api/requests': () => json({ error: { code: 'server_error', message: 'Database is down' } }, 500),
    });

    renderApp();

    expect(await screen.findByRole('alert')).toHaveTextContent('Database is down');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('keeps the statistics page closed to standard users', async () => {
    stubApi({ '/api/auth/me': () => json({ ...ADMIN, role: 'user', display_name: 'Shinji Ikari' }) });

    renderApp('/admin');

    expect(await screen.findByText('Administrators only')).toBeInTheDocument();
  });

  it('shows a not-found state for an unknown route', async () => {
    stubApi({ '/api/auth/me': () => json(null) });

    renderApp('/nope');

    await waitFor(() => expect(screen.getByText('Page not found')).toBeInTheDocument());
  });
});
