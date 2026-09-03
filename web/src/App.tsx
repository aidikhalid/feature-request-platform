import { Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom';

import { useLogout, useMe } from './api/hooks';
import { AdminPage } from './pages/AdminPage';
import { LoginPage, RegisterPage } from './pages/AuthPages';
import { BrowsePage } from './pages/BrowsePage';
import { NewRequestPage } from './pages/NewRequestPage';
import { RequestDetailPage } from './pages/RequestDetailPage';
import { EmptyState } from './components/Feedback';

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Routes>
          <Route path="/" element={<BrowsePage />} />
          <Route path="/requests/new" element={<NewRequestPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/index.html" element={<Navigate to="/" replace />} />
          <Route
            path="*"
            element={
              <EmptyState title="Page not found">
                <Link className="btn" to="/">
                  Back to requests
                </Link>
              </EmptyState>
            }
          />
        </Routes>
      </main>
    </>
  );
}

function Header() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();

  return (
    <header className="header">
      <div className="header-inner">
        <Link className="brand" to="/">
          Feature Requests
        </Link>
        <nav aria-label="Main">
          {me ? (
            <>
              {me.role === 'admin' && <Link to="/admin">Statistics</Link>}
              <span className="who">
                {me.display_name}
                {me.role === 'admin' ? ' (admin)' : ''}
              </span>
              <button
                type="button"
                className="btn"
                onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/') })}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login">Sign in</Link>
              <Link className="btn" to="/register">
                Create account
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
