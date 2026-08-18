import { beforeEach, describe, expect, it, vi } from 'vitest';

const env = import.meta.env;

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
  getApps: vi.fn(() => []),
}));

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({})),
  GoogleAuthProvider: vi.fn(() => ({})),
  signInWithPopup: vi.fn().mockResolvedValue({ user: { getIdToken: vi.fn().mockResolvedValue('google-token') } }),
  RecaptchaVerifier: vi.fn(() => ({ clear: vi.fn() })),
  signInWithPhoneNumber: vi.fn(),
}));

import { signInWithGoogleProvider, verifyPhoneCode } from '../services/firebaseClient';

describe('firebase client helpers', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'window', {
      value: { document: { getElementById: vi.fn(() => ({})) } },
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

  it('returns a phone verification code from the confirmation result', async () => {
    const confirmMock = vi.fn().mockResolvedValue({ user: { getIdToken: vi.fn().mockResolvedValue('phone-token') } });
    const session = { confirmationResult: { confirm: confirmMock }, verifier: { clear: vi.fn() } } as never;
    const token = await verifyPhoneCode(session, '123456');
    expect(token).toBe('phone-token');
    expect(confirmMock).toHaveBeenCalledWith('123456');
  });
});
