import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';

import { api, buildQuery, ApiError } from './client';
import type {
  Comment,
  FeatureRequestDetail,
  FeatureRequestSummary,
  ListParams,
  Page,
  RequestStatus,
  Stats,
  User,
  VoteState,
} from './types';

/**
 * Query keys in one place.
 *
 * Almost all of this application's state is a cache of server data, not application
 * state, which is why there is no Redux store here: React Query owns the server cache
 * (fetching, staleness, retries, loading and error flags) and React's own state handles
 * the genuinely local things — form fields and dialog open/closed.
 */
export const keys = {
  me: ['me'] as const,
  requests: (params: ListParams) => ['requests', params] as const,
  request: (id: number) => ['request', id] as const,
  comments: (id: number) => ['comments', id] as const,
  stats: ['stats'] as const,
};

/* ---------------------------------- auth ---------------------------------- */

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      try {
        return await api.get<User>('/api/auth/me');
      } catch (error) {
        // Not being signed in is a normal state for a visitor, not an error to surface.
        if (error instanceof ApiError && error.isUnauthenticated) return null;
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

export function useLogin(client: QueryClient = useQueryClient()) {
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<User>('/api/auth/login', body),
    onSuccess: (user) => {
      client.setQueryData(keys.me, user);
      // Vote state is per-user, so every cached list and detail is now stale.
      void client.invalidateQueries();
    },
  });
}

export function useRegister(client: QueryClient = useQueryClient()) {
  return useMutation({
    mutationFn: (body: { email: string; display_name: string; password: string }) =>
      api.post<User>('/api/auth/register', body),
    onSuccess: (user) => {
      client.setQueryData(keys.me, user);
      void client.invalidateQueries();
    },
  });
}

export function useLogout(client: QueryClient = useQueryClient()) {
  return useMutation({
    mutationFn: () => api.post<void>('/api/auth/logout'),
    onSuccess: () => {
      client.setQueryData(keys.me, null);
      void client.invalidateQueries();
    },
  });
}

/* -------------------------------- requests -------------------------------- */

export function useRequests(params: ListParams) {
  return useQuery({
    queryKey: keys.requests(params),
    queryFn: () =>
      api.get<Page<FeatureRequestSummary>>(
        `/api/requests${buildQuery({
          q: params.q,
          status: params.status,
          sort: params.sort,
          page: params.page,
        })}`,
      ),
    // Keeps the previous page visible while the next one loads, so changing a filter
    // does not blank the screen.
    placeholderData: (previous) => previous,
  });
}

export function useRequest(id: number) {
  return useQuery({
    queryKey: keys.request(id),
    queryFn: () => api.get<FeatureRequestDetail>(`/api/requests/${id}`),
  });
}

export function useCreateRequest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description: string }) =>
      api.post<FeatureRequestDetail>('/api/requests', body),
    onSuccess: (created) => {
      client.setQueryData(keys.request(created.id), created);
      void client.invalidateQueries({ queryKey: ['requests'] });
    },
  });
}

export function useUpdateRequest(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; description?: string }) =>
      api.patch<FeatureRequestDetail>(`/api/requests/${id}`, body),
    onSuccess: (updated) => {
      client.setQueryData(keys.request(id), updated);
      void client.invalidateQueries({ queryKey: ['requests'] });
    },
  });
}

/* ---------------------------------- votes --------------------------------- */

/** Apply a vote result (real or predicted) to every cache holding this request. */
function writeVoteState(client: QueryClient, state: VoteState) {
  const { feature_request_id: id, vote_count, has_voted } = state;

  client.setQueryData<FeatureRequestDetail>(keys.request(id), (previous) =>
    previous ? { ...previous, vote_count, has_voted } : previous,
  );

  client.setQueriesData<Page<FeatureRequestSummary>>({ queryKey: ['requests'] }, (previous) =>
    previous
      ? {
          ...previous,
          items: previous.items.map((item) =>
            item.id === id ? { ...item, vote_count, has_voted } : item,
          ),
        }
      : previous,
  );
}

/**
 * Vote and un-vote, applied optimistically.
 *
 * The button state flips the instant it is clicked, because waiting on a round trip for
 * something this small feels broken. If the server disagrees we put the old value back.
 *
 * Safe to fire repeatedly: the endpoints are idempotent server-side (the vote row is
 * inserted with ON CONFLICT DO NOTHING), so a double-click cannot create two votes —
 * the optimistic UI and the API agree on the outcome.
 */
export function useToggleVote(request: { id: number; has_voted: boolean; vote_count: number }) {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (nextVoted: boolean) =>
      nextVoted
        ? api.post<VoteState>(`/api/requests/${request.id}/vote`)
        : api.delete<VoteState>(`/api/requests/${request.id}/vote`),

    onMutate: async (nextVoted) => {
      // Stop any in-flight refetch from overwriting the optimistic value.
      await client.cancelQueries({ queryKey: keys.request(request.id) });

      const rollback = {
        detail: client.getQueryData<FeatureRequestDetail>(keys.request(request.id)),
        lists: client.getQueriesData<Page<FeatureRequestSummary>>({ queryKey: ['requests'] }),
      };

      writeVoteState(client, {
        feature_request_id: request.id,
        has_voted: nextVoted,
        vote_count: request.vote_count + (nextVoted ? 1 : -1),
      });

      return rollback;
    },

    onError: (_error, _variables, rollback) => {
      if (!rollback) return;
      if (rollback.detail) client.setQueryData(keys.request(request.id), rollback.detail);
      for (const [key, value] of rollback.lists) client.setQueryData(key, value);
    },

    // Whatever happened, finish on the server's number rather than our guess.
    onSuccess: (state) => writeVoteState(client, state),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.stats });
    },
  });
}

/* -------------------------------- comments -------------------------------- */

export function useComments(id: number) {
  return useQuery({
    queryKey: keys.comments(id),
    queryFn: () => api.get<Comment[]>(`/api/requests/${id}/comments`),
  });
}

export function useAddComment(id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => api.post<Comment>(`/api/requests/${id}/comments`, { body }),
    onSuccess: () => {
      // The comment count lives on the request, so both caches need refreshing.
      void client.invalidateQueries({ queryKey: keys.comments(id) });
      void client.invalidateQueries({ queryKey: keys.request(id) });
      void client.invalidateQueries({ queryKey: ['requests'] });
    },
  });
}

/* ---------------------------------- admin --------------------------------- */

function useAdminMutation<TBody>(
  id: number,
  send: (body: TBody) => Promise<FeatureRequestDetail>,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: send,
    onSuccess: (updated) => {
      client.setQueryData(keys.request(id), updated);
      void client.invalidateQueries({ queryKey: ['requests'] });
      void client.invalidateQueries({ queryKey: keys.stats });
    },
  });
}

export function useSetStatus(id: number) {
  return useAdminMutation(id, (status: RequestStatus) =>
    api.patch<FeatureRequestDetail>(`/api/admin/requests/${id}/status`, { status }),
  );
}

export function useSetOfficialResponse(id: number) {
  return useAdminMutation(id, (body: string) =>
    api.put<FeatureRequestDetail>(`/api/admin/requests/${id}/response`, { body }),
  );
}

export function useMergeRequest(sourceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      api.post<FeatureRequestDetail>(`/api/admin/requests/${sourceId}/merge`, {
        target_id: targetId,
      }),
    onSuccess: () => {
      // A merge moves votes and comments between two requests, so rather than patch
      // caches by hand we refetch: correctness over cleverness for a rare admin action.
      void client.invalidateQueries();
    },
  });
}

export function useStats(enabled: boolean) {
  return useQuery({ queryKey: keys.stats, queryFn: () => api.get<Stats>('/api/admin/stats'), enabled });
}
