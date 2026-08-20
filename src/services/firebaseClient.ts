import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  signInWithPopup,
  type ConfirmationResult,
  type UserCredential,
} from 'firebase/auth';

const getFirebaseConfig = () => ({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
});

export function isFirebaseConfigured(): boolean {
  const firebaseConfig = getFirebaseConfig();
  return Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId) || import.meta.env.MODE === 'test';
}

const hasFirebaseConfig = isFirebaseConfigured();

export function normalizeIndianPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  if (/^0?[6-9]\d{9}$/.test(digits)) return `+91${digits.slice(-10)}`;
  if (/^91[6-9]\d{9}$/.test(digits)) return `+${digits}`;
  throw new Error('Enter a valid 10-digit Indian mobile number.');
}

function getOrCreateApp(): FirebaseApp {
  if (typeof window === 'undefined') {
    throw new Error('Firebase authentication requires a browser environment.');
  }
  const existing = getApps();
  if (existing.length > 0) {
    return existing[0];
  }
  const firebaseConfig = getFirebaseConfig();
  if (!Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId)) {
    throw new Error('Firebase authentication is not configured.');
  }
  return initializeApp(firebaseConfig);
}

export interface PhoneVerificationSession {
  confirmationResult: ConfirmationResult;
  verifier: RecaptchaVerifier;
}

export async function signInWithGoogleProvider(): Promise<string> {
  const auth = getAuth(getOrCreateApp());
  const provider = new GoogleAuthProvider();
  const result = await signInWithPopup(auth, provider);
  return result.user.getIdToken();
}

export async function startPhoneVerification(phone: string): Promise<PhoneVerificationSession> {
  const auth = getAuth(getOrCreateApp());
  const container = document.getElementById('recaptcha-container');
  if (!container) {
    throw new Error('The reCAPTCHA container is unavailable.');
  }

  const verifier = new RecaptchaVerifier(auth, container, {
    size: 'invisible',
    callback: () => undefined,
  });

  try {
    const confirmationResult = await signInWithPhoneNumber(auth, normalizeIndianPhone(phone), verifier);
    return { confirmationResult, verifier };
  } catch (cause) {
    try {
      verifier.clear();
    } catch {
      // Preserve Firebase's actionable error if best-effort cleanup also fails.
    }
    throw cause;
  }
}

export async function verifyPhoneCode(session: PhoneVerificationSession, code: string): Promise<string> {
  const credential = await session.confirmationResult.confirm(code);
  return credential.user.getIdToken();
}

export async function clearPhoneVerification(session?: PhoneVerificationSession): Promise<void> {
  if (session?.verifier) {
    session.verifier.clear();
  }
}
