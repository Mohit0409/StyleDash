import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getAuth, type Auth } from 'firebase/auth'
import { getFirestore, type Firestore } from 'firebase/firestore'
import { getStorage, type FirebaseStorage } from 'firebase/storage'
import { getAnalytics, isSupported, type Analytics } from 'firebase/analytics'

// Replace with your actual Firebase project config.
// Get this from: Firebase Console → Project Settings → General → Your apps → SDK setup
// IMPORTANT: measurementId is required for Analytics to work.
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || '',
}

// True only when the config looks real (not empty strings / placeholder
// values from .env.example). Without this guard, an unconfigured project
// would call initializeApp/getAuth/getFirestore with empty strings, which
// throws synchronously at module load and blanks the entire app — before
// React even gets a chance to render.
const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
  firebaseConfig.projectId &&
  firebaseConfig.appId &&
  !firebaseConfig.apiKey.startsWith('your_')
)

let app: FirebaseApp | null = null
export let auth: Auth | null = null
export let db: Firestore | null = null
export let storage: FirebaseStorage | null = null
export let analytics: Analytics | null = null

if (isFirebaseConfigured) {
  try {
    app = initializeApp(firebaseConfig)
    auth = getAuth(app)
    db = getFirestore(app)
    storage = getStorage(app)

    // Analytics only works in a real browser with measurementId configured —
    // guard with isSupported() so it never throws during SSR, tests, or local
    // dev without Firebase configured.
    isSupported()
      .then(supported => {
        if (supported && app && firebaseConfig.measurementId) {
          analytics = getAnalytics(app)
        }
      })
      .catch(() => {
        // Silently ignore — analytics is optional and shouldn't break the app
        analytics = null
      })
  } catch (err) {
    // Defensive: if Firebase still throws for some other reason (bad keys,
    // network restrictions, etc.), log it but never let it take down the app.
    console.error('Firebase failed to initialize — Firebase features will be disabled:', err)
    app = null
    auth = null
    db = null
    storage = null
  }
} else {
  console.warn(
    '[firebase/config] No Firebase config found (.env.local is missing or incomplete). ' +
    'Firebase Auth/Firestore/Storage/Analytics are disabled. ' +
    'Copy .env.example to .env.local and fill in your project values to enable them.'
  )
}

export default app