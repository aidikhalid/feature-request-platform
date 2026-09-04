import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useLogin, useRegister } from '../api/hooks';
import { ApiError } from '../api/client';
import { InlineError } from '../components/Feedback';

const DEMO_ACCOUNTS = [
  { email: 'admin@example.com', label: 'Administrator' },
  { email: 'shinji@example.com', label: 'Standard user' },
];

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    login.mutate({ email, password }, { onSuccess: () => navigate('/') });
  };

  return (
    <div style={{ maxWidth: '26rem', margin: '0 auto' }}>
      <h1>Sign in</h1>
      <form className="card stack" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <InlineError error={login.error} />
        <button type="submit" className="btn btn-primary" disabled={login.isPending}>
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="small subtle" style={{ margin: 0 }}>
          No account? <Link to="/register">Create one</Link>.
        </p>
      </form>

      {/* Development convenience: the seeded accounts, so a reviewer can get straight in. */}
      <div className="notice notice-info small" style={{ marginTop: '1rem' }}>
        <strong>Demo accounts</strong> (password <code>Password123!</code>)
        <ul style={{ margin: '0.4rem 0 0', paddingLeft: '1.1rem' }}>
          {DEMO_ACCOUNTS.map((account) => (
            <li key={account.email}>
              <button
                type="button"
                className="btn-link"
                onClick={() => {
                  setEmail(account.email);
                  setPassword('Password123!');
                }}
              >
                {account.email}
              </button>{' '}
              — {account.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const register = useRegister();
  const [form, setForm] = useState({ email: '', display_name: '', password: '' });

  const fieldErrors = register.error instanceof ApiError ? register.error.fieldErrors : {};
  const set = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((previous) => ({ ...previous, [key]: event.target.value }));

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    register.mutate(form, { onSuccess: () => navigate('/') });
  };

  return (
    <div style={{ maxWidth: '26rem', margin: '0 auto' }}>
      <h1>Create an account</h1>
      <form className="card stack" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="reg-name">Display name</label>
          <input id="reg-name" required value={form.display_name} onChange={set('display_name')} />
          {fieldErrors.display_name && <p className="field-error">{fieldErrors.display_name}</p>}
        </div>
        <div className="field">
          <label htmlFor="reg-email">Email</label>
          <input
            id="reg-email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={set('email')}
          />
          {fieldErrors.email && <p className="field-error">{fieldErrors.email}</p>}
        </div>
        <div className="field">
          <label htmlFor="reg-password">Password</label>
          <input
            id="reg-password"
            type="password"
            autoComplete="new-password"
            required
            value={form.password}
            onChange={set('password')}
          />
          <p className="subtle small" style={{ margin: '0.25rem 0 0' }}>
            At least 8 characters.
          </p>
          {fieldErrors.password && <p className="field-error">{fieldErrors.password}</p>}
        </div>
        {register.error instanceof ApiError && register.error.status !== 422 && (
          <InlineError error={register.error} />
        )}
        <button type="submit" className="btn btn-primary" disabled={register.isPending}>
          {register.isPending ? 'Creating account…' : 'Create account'}
        </button>
        <p className="small subtle" style={{ margin: 0 }}>
          Already registered? <Link to="/login">Sign in</Link>.
        </p>
      </form>
    </div>
  );
}
