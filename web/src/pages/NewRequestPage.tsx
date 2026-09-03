import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useCreateRequest, useMe } from '../api/hooks';
import { InlineError, Skeleton } from '../components/Feedback';

export function NewRequestPage() {
  const navigate = useNavigate();
  const { data: me, isPending } = useMe();
  const create = useCreateRequest();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  if (isPending) return <Skeleton rows={1} />;

  if (!me) {
    return (
      <p className="notice notice-info">
        <Link to="/login">Sign in</Link> to submit a feature request.
      </p>
    );
  }

  // Field-level messages come straight from the server's validation envelope, so the
  // rules shown to the user are the rules actually enforced.
  const fieldErrors = create.error instanceof ApiError ? create.error.fieldErrors : {};

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    create.mutate(
      { title, description },
      { onSuccess: (created) => navigate(`/requests/${created.id}`) },
    );
  };

  return (
    <>
      <h1>Submit a feature request</h1>
      <p className="subtle">
        Describe the problem you are trying to solve. Requests start under review.
      </p>

      <form className="card stack" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="title">Title</label>
          <input
            id="title"
            value={title}
            maxLength={200}
            required
            aria-describedby={fieldErrors.title ? 'title-error' : undefined}
            aria-invalid={Boolean(fieldErrors.title)}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Short summary of the idea"
          />
          {fieldErrors.title && (
            <p className="field-error" id="title-error">
              {fieldErrors.title}
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            value={description}
            maxLength={5000}
            required
            aria-describedby={fieldErrors.description ? 'description-error' : undefined}
            aria-invalid={Boolean(fieldErrors.description)}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What are you trying to do, and what gets in the way?"
          />
          {fieldErrors.description && (
            <p className="field-error" id="description-error">
              {fieldErrors.description}
            </p>
          )}
        </div>

        {create.error instanceof ApiError && create.error.status !== 422 && (
          <InlineError error={create.error} />
        )}

        <div className="admin-row">
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {create.isPending ? 'Submitting…' : 'Submit request'}
          </button>
          <Link className="btn" to="/">
            Cancel
          </Link>
        </div>
      </form>
    </>
  );
}
