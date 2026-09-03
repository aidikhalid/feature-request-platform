// Mirrors the Pydantic response schemas on the API side. Keeping these in one file makes
// the API contract explicit and gives the compiler something to check every component
// against; the honest next step is generating them from the published OpenAPI schema.

export type RequestStatus =
  | 'under_review'
  | 'planned'
  | 'in_progress'
  | 'released'
  | 'declined';

export const STATUSES: RequestStatus[] = [
  'under_review',
  'planned',
  'in_progress',
  'released',
  'declined',
];

export const STATUS_LABELS: Record<RequestStatus, string> = {
  under_review: 'Under Review',
  planned: 'Planned',
  in_progress: 'In Progress',
  released: 'Released',
  declined: 'Declined',
};

export type SortOption = 'top' | 'new' | 'discussed';

export interface Author {
  id: number;
  display_name: string;
}

export interface User extends Author {
  email: string;
  role: 'user' | 'admin';
  created_at: string;
}

export interface FeatureRequestSummary {
  id: number;
  title: string;
  status: RequestStatus;
  vote_count: number;
  comment_count: number;
  created_at: string;
  author: Author;
  merged_into_id: number | null;
  has_voted: boolean;
}

export interface FeatureRequestDetail extends FeatureRequestSummary {
  description: string;
  official_response: string | null;
  official_response_at: string | null;
  official_response_by: Author | null;
  updated_at: string;
}

export interface Comment {
  id: number;
  body: string;
  created_at: string;
  author: Author;
}

export interface VoteState {
  feature_request_id: number;
  vote_count: number;
  has_voted: boolean;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Stats {
  total_requests: number;
  total_votes: number;
  total_comments: number;
  requests_last_7_days: number;
  by_status: Record<RequestStatus, number>;
  top_requests: { id: number; title: string; vote_count: number }[];
}

export interface ListParams {
  q?: string;
  status?: RequestStatus | '';
  sort?: SortOption;
  page?: number;
}
