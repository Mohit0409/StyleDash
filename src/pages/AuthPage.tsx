import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';

export const AuthPage: React.FC<{ mode: 'login' | 'register' }> = ({ mode }) => {
  const { login, register, error, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destination = (location.state as { from?: string } | null)?.from || '/profile';
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const success = mode === 'login'
      ? await login(email, password)
      : await register(name, email, password, phone || undefined);
    if (success) navigate(destination, { replace: true });
  };

  return <div className="max-w-md mx-auto px-4 py-12">
    <SEO title={`${mode === 'login' ? 'Login' : 'Register'} - StyleDash`} />
    <form onSubmit={submit} className="bg-white dark:bg-neutral-900 border dark:border-neutral-800 rounded-3xl p-7 space-y-4 shadow-sm">
      <h1 className="text-2xl font-black">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
      {mode === 'register' && <>
        <input required minLength={2} maxLength={80} autoComplete="name" value={name} onChange={event => setName(event.target.value)} placeholder="Full name" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
        <input minLength={10} maxLength={20} autoComplete="tel" value={phone} onChange={event => setPhone(event.target.value)} placeholder="Phone number" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      </>}
      <input required type="email" autoComplete="email" maxLength={254} value={email} onChange={event => setEmail(event.target.value)} placeholder="Email" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      <input required type="password" minLength={12} maxLength={256} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={event => setPassword(event.target.value)} placeholder="Password (12+ characters)" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      {mode === 'register' && <p className="text-xs text-neutral-500">Use at least 12 characters. Long passphrases and password-manager passwords are supported.</p>}
      {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
      <button disabled={loading} className="w-full p-3 rounded-xl bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold disabled:opacity-60">{loading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Register'}</button>
      <p className="text-xs text-center">{mode === 'login' ? <><Link className="text-lime-600 font-bold" to="/forgot-password">Forgot password?</Link><span className="mx-2 text-neutral-400">·</span>New here? <Link className="text-lime-600 font-bold" to="/register" state={{ from: destination }}>Register</Link></> : <>Already registered? <Link className="text-lime-600 font-bold" to="/login" state={{ from: destination }}>Login</Link></>}</p>
    </form>
  </div>;
};
