import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { authApi } from '../services/authApi';
import { ApiError } from '../services/apiClient';

const GENERIC_REQUEST_MESSAGE = 'If an account exists, reset instructions will be sent shortly.';

export const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true); setError(''); setMessage('');
    try {
      await authApi.requestPasswordReset(email);
      setMessage(GENERIC_REQUEST_MESSAGE);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Password reset could not be requested. Please try again.');
    } finally { setSubmitting(false); }
  };

  return <div className="max-w-md mx-auto px-4 py-12">
    <SEO title="Reset password - StyleDash" />
    <form onSubmit={submit} className="bg-white dark:bg-neutral-900 border dark:border-neutral-800 rounded-3xl p-7 space-y-4 shadow-sm">
      <h1 className="text-2xl font-black">Reset your password</h1>
      <p className="text-sm text-neutral-500">Enter your account email. For privacy, the result is the same whether or not an account exists.</p>
      <input required type="email" autoComplete="email" maxLength={254} value={email} onChange={event => setEmail(event.target.value)} placeholder="Email address" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      <button disabled={submitting} className="w-full p-3 rounded-xl bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold disabled:opacity-60">{submitting ? 'Please wait…' : 'Send reset instructions'}</button>
      <p className="text-xs text-center"><Link className="text-lime-600 font-bold" to="/login">Back to login</Link></p>
    </form>
  </div>;
};

export const ResetPassword: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get('token') || '');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [complete, setComplete] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (location.hash) navigate('/reset-password', { replace: true });
  }, [location.hash, navigate]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!token) { setError('This password reset link is invalid or has expired.'); return; }
    if (password.length < 12 || password.length > 256) { setError('Password must be 12–256 characters.'); return; }
    if (password !== confirmation) { setError('Passwords do not match.'); return; }
    setSubmitting(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      setPassword(''); setConfirmation(''); setComplete(true);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Password could not be reset. Please try again.');
    } finally { setSubmitting(false); }
  };

  return <div className="max-w-md mx-auto px-4 py-12">
    <SEO title="Choose a new password - StyleDash" />
    <section className="bg-white dark:bg-neutral-900 border dark:border-neutral-800 rounded-3xl p-7 space-y-4 shadow-sm">
      <h1 className="text-2xl font-black">Choose a new password</h1>
      {!token ? <><p role="alert" className="text-sm text-red-600">This password reset link is invalid or has expired.</p><Link className="text-sm text-lime-600 font-bold" to="/forgot-password">Request a new link</Link></> : complete ? <><p role="status" className="text-sm text-green-700">Your password has been reset. Please sign in.</p><Link className="block w-full text-center p-3 rounded-xl bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold" to="/login" replace>Go to login</Link></> : <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-neutral-500">Use a new password with 12–256 characters.</p>
        <input required type="password" autoComplete="new-password" minLength={12} maxLength={256} value={password} onChange={event => setPassword(event.target.value)} placeholder="New password" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
        <input required type="password" autoComplete="new-password" minLength={12} maxLength={256} value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Confirm new password" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button disabled={submitting} className="w-full p-3 rounded-xl bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold disabled:opacity-60">{submitting ? 'Please wait…' : 'Reset password'}</button>
      </form>}
    </section>
  </div>;
};
