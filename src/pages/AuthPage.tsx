import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';
import { clearPhoneVerification, normalizeIndianPhone, signInWithGoogleProvider, startPhoneVerification, verifyPhoneCode, type PhoneVerificationSession } from '../services/firebaseClient';

export const AuthPage: React.FC<{ mode: 'login' | 'register' }> = ({ mode }) => {
  const { login, register, federatedLogin, error, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const destination = (location.state as { from?: string } | null)?.from || '/profile';
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [otpBusy, setOtpBusy] = useState(false);
  const [phoneSession, setPhoneSession] = useState<PhoneVerificationSession | null>(null);
  const [providerBusy, setProviderBusy] = useState<'google' | 'phone' | null>(null);
  const [providerError, setProviderError] = useState('');
  const [resendIn, setResendIn] = useState(0);

  useEffect(() => {
    if (!resendIn) return undefined;
    const timer = window.setInterval(() => setResendIn(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [resendIn]);

  useEffect(() => () => {
    void clearPhoneVerification(phoneSession ?? undefined);
  }, [phoneSession]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const success = mode === 'login'
      ? await login(email, password)
      : await register(name, email, password, phone || undefined);
    if (success) navigate(destination, { replace: true });
  };

  const handleGoogle = async () => {
    setProviderBusy('google');
    setProviderError('');
    try {
      const idToken = await signInWithGoogleProvider();
      const success = await federatedLogin('google', idToken);
      if (success) navigate(destination, { replace: true });
    } catch (cause) {
      setProviderError(cause instanceof Error ? cause.message : 'Google sign in could not be completed.');
    } finally {
      setProviderBusy(null);
    }
  };

  const handlePhoneStart = async () => {
    if (!phone.trim()) return;
    setOtpBusy(true);
    setProviderError('');
    try {
      normalizeIndianPhone(phone);
      const session = await startPhoneVerification(phone);
      setPhoneSession(session);
      setOtpSent(true);
      setOtpCode('');
      setResendIn(30);
    } catch (cause) {
      setProviderError(cause instanceof Error ? cause.message : 'OTP could not be sent.');
      setOtpSent(false);
    } finally {
      setOtpBusy(false);
    }
  };

  const handlePhoneConfirm = async () => {
    if (!phoneSession || !otpCode.trim()) return;
    setProviderBusy('phone');
    setProviderError('');
    try {
      const idToken = await verifyPhoneCode(phoneSession, otpCode);
      const success = await federatedLogin('phone', idToken);
      if (success) navigate(destination, { replace: true });
    } catch (cause) {
      setProviderError(cause instanceof Error ? cause.message : 'OTP verification failed.');
    } finally {
      setProviderBusy(null);
    }
  };

  const changePhone = async () => {
    await clearPhoneVerification(phoneSession ?? undefined);
    setPhoneSession(null); setOtpSent(false); setOtpCode(''); setResendIn(0); setProviderError('');
  };

  return <div className="max-w-md mx-auto px-4 py-12">
    <SEO title={`${mode === 'login' ? 'Login' : 'Register'} - StyleDash`} />
    <div className="bg-white dark:bg-neutral-900 border dark:border-neutral-800 rounded-3xl p-7 space-y-4 shadow-sm">
      <h1 className="text-2xl font-black">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
      <div className="space-y-2">
        <button type="button" disabled={providerBusy === 'google' || loading} onClick={handleGoogle} className="w-full rounded-xl border border-neutral-300 px-3 py-3 font-semibold disabled:opacity-60">{providerBusy === 'google' ? 'Please wait…' : 'Continue with Google'}</button>
        <div className="rounded-2xl border border-neutral-200 p-3 space-y-3">
          <input minLength={10} maxLength={20} autoComplete="tel" value={phone} onChange={event => setPhone(event.target.value)} placeholder="Mobile number" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
          {!otpSent ? <button type="button" disabled={otpBusy || loading} onClick={handlePhoneStart} className="w-full rounded-xl bg-neutral-950 px-3 py-3 font-semibold text-white disabled:opacity-60">{otpBusy ? 'Sending OTP…' : 'Continue with Mobile'}</button> : <>
            <p className="text-xs text-neutral-500">Code sent to {phone.replace(/(\d{2})\d+(\d{2})$/, '$1******$2')}</p>
            <input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={otpCode} onChange={event => setOtpCode(event.target.value.replace(/\D/g, ''))} placeholder="Enter OTP" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
            <button type="button" disabled={providerBusy === 'phone' || loading} onClick={handlePhoneConfirm} className="w-full rounded-xl bg-lime-600 px-3 py-3 font-semibold text-white disabled:opacity-60">{providerBusy === 'phone' ? 'Verifying…' : 'Verify OTP'}</button>
            <div className="flex justify-between text-xs"><button type="button" disabled={otpBusy || resendIn > 0} onClick={handlePhoneStart} className="font-bold text-lime-600">{resendIn ? `Resend in ${resendIn}s` : 'Resend OTP'}</button><button type="button" onClick={changePhone} className="font-bold text-lime-600">Change number</button></div>
          </>}
          <div id="recaptcha-container" />
        </div>
      </div>
      {(error || providerError) && <p role="alert" className="text-sm text-red-600">{error || providerError}</p>}
      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.24em] text-neutral-500"><span className="h-px flex-1 bg-neutral-200" />or<span className="h-px flex-1 bg-neutral-200" /></div>
      <form onSubmit={submit} className="space-y-4">
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
    </div>
  </div>;
};
