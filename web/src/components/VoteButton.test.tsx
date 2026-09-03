import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { keys, useRequest } from '../api/hooks';
import type { FeatureRequestDetail } from '../api/types';
import { VoteButton } from './VoteButton';

const REQUEST: FeatureRequestDetail = {
  id: 1,
  title: 'Dark mode',
  description: 'Please add a dark theme.',
  status: 'under_review',
  vote_count: 4,
  comment_count: 0,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  author: { id: 9, display_name: 'Alice' },
  merged_into_id: null,
  has_voted: false,
  official_response: null,
  official_response_at: null,
  official_response_by: null,
};

/**
 * Renders the button the way the detail page does — reading the request from the query
 * cache — so the test exercises the real path an optimistic update travels: mutation
 * writes to the cache, the subscribed component re-renders.
 */
function Harness({ client }: { client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <Subject />
    </QueryClientProvider>
  );
}

function Subject() {
  const { data } = useRequest(REQUEST.id);
  if (!data) return null;
  return <VoteButton request={data} canVote />;
}

function makeClient(overrides: Partial<FeatureRequestDetail> = {}) {
  const client = new QueryClient({
    defaultOptions: {
      // staleTime keeps the seeded cache entry from triggering a background refetch, so
      // the only fetch calls these tests see are the ones the mutation makes.
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  client.setQueryData(keys.request(REQUEST.id), { ...REQUEST, ...overrides });
  return client;
}

/** A promise we can resolve by hand, to inspect the UI mid-flight. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('VoteButton', () => {
  it('shows the vote count and reports its pressed state to assistive technology', () => {
    render(<Harness client={makeClient()} />);
    const button = screen.getByRole('button');

    expect(button).toHaveAttribute('aria-pressed', 'false');
    expect(button).toHaveAccessibleName(/Vote for “Dark mode”\. 4 votes\./);
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('updates immediately on click, before the server has answered', async () => {
    const pending = deferred<Response>();
    vi.mocked(fetch).mockReturnValue(pending.promise);

    render(<Harness client={makeClient()} />);
    await userEvent.click(screen.getByRole('button'));

    // No await on the request: this is the optimistic state.
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('5')).toBeInTheDocument();

    pending.resolve(
      new Response(JSON.stringify({ feature_request_id: 1, vote_count: 5, has_voted: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument());
  });

  it('settles on the server total even when it differs from the prediction', async () => {
    // Someone else voted at the same time: the server says 9, not our predicted 5.
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ feature_request_id: 1, vote_count: 9, has_voted: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    render(<Harness client={makeClient()} />);
    await userEvent.click(screen.getByRole('button'));

    await waitFor(() => expect(screen.getByText('9')).toBeInTheDocument());
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('rolls back when the server rejects the vote', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'unauthorized', message: 'Nope' } }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    render(<Harness client={makeClient()} />);
    await userEvent.click(screen.getByRole('button'));

    await waitFor(() =>
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false'),
    );
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('removes an existing vote with a DELETE', async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ feature_request_id: 1, vote_count: 3, has_voted: false }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    render(<Harness client={makeClient({ has_voted: true, vote_count: 4 })} />);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(button);

    expect(vi.mocked(fetch).mock.calls[0]?.[1]).toMatchObject({ method: 'DELETE' });
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument());
  });

  it('cannot be used on a request that has been merged away', async () => {
    render(<Harness client={makeClient({ merged_into_id: 2 })} />);

    expect(screen.getByRole('button')).toBeDisabled();
    await userEvent.click(screen.getByRole('button'));
    expect(fetch).not.toHaveBeenCalled();
  });

  it('asks a signed-out visitor to sign in instead of calling the API', async () => {
    const onRequireSignIn = vi.fn();
    const client = makeClient();
    render(
      <QueryClientProvider client={client}>
        <VoteButton request={REQUEST} canVote={false} onRequireSignIn={onRequireSignIn} />
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getByRole('button'));

    expect(onRequireSignIn).toHaveBeenCalledOnce();
    expect(fetch).not.toHaveBeenCalled();
  });
});
