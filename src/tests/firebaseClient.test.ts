import { beforeEach, describe, expect, it, vi } from 'vitest';

const env = import.meta.env;
const firebaseAuthMocks = vi.hoisted(() => ({
  clearRecaptcha: vi.fn(),
  signInWithPhoneNumber: vi.fn(),
}));

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
  getApps: vi.fn(() => []),
}));

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({})),
  GoogleAuthProvider: vi.fn(() => ({})),
  signInWithPopup: vi.fn().mockResolvedValue({ user: { getIdToken: vi.fn().mockResolvedValue('google-token') } }),
  RecaptchaVerifier: vi.fn(() => ({ clear: firebaseAuthMocks.clearRecaptcha })),
  signInWithPhoneNumber: firebaseAuthMocks.signInWithPhoneNumber,
}));

import { normalizeIndianPhone, signInWithGoogleProvider, startPhoneVerification, verifyPhoneCode } from '../services/firebaseClient';

describe('firebase client helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(globalThis, 'window', {
      value: { document: { getElementById: vi.fn(() => ({})) } },
      configurable: true,
    });
    Object.defineProperty(globalThis, 'document', {
      value: { getElementById: vi.fn(() => ({})) },
      configurable: true,
    });
    vi.stubEnv('VITE_FIREBASE_API_KEY', 'key');
    vi.stubEnv('VITE_FIREBASE_AUTH_DOMAIN', 'example.firebaseapp.com');
    vi.stubEnv('VITE_FIREBASE_PROJECT_ID', 'project');
    vi.stubEnv('VITE_FIREBASE_APP_ID', 'app');
  });

  it('requests a Google ID token from Firebase popup auth', async () => {
    const token = await signInWithGoogleProvider();
    expect(token).toBe('google-token');
  });

  it('returns the verified phone credential ID token from the confirmation result', async () => {
    const confirmMock = vi.fn().mockResolvedValue({ user: { getIdToken: vi.fn().mockResolvedValue('phone-token') } });
    const session = { confirmationResult: { confirm: confirmMock }, verifier: { clear: vi.fn() } } as never;
    const token = await verifyPhoneCode(session, '123456');
    expect(token).toBe('phone-token');
    expect(confirmMock).toHaveBeenCalledWith('123456');
  });

  it('normalizes the supported Indian test-number formats without accepting malformed values', () => {
    expect(normalizeIndianPhone('+91 99999 99999')).toBe('+919999999999');
    expect(normalizeIndianPhone('09999999999')).toBe('+919999999999');
    expect(() => normalizeIndianPhone('12345')).toThrow('valid 10-digit Indian mobile number');
  });

  it('clears reCAPTCHA when Firebase rejects the OTP send before returning a session', async () => {
    firebaseAuthMocks.signInWithPhoneNumber.mockRejectedValueOnce(new Error('OTP send failed'));

    await expect(startPhoneVerification('+91 99999 99999')).rejects.toThrow('OTP send failed');

    expect(firebaseAuthMocks.clearRecaptcha).toHaveBeenCalledTimes(1);
  });
});
