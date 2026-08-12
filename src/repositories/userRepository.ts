import { UserProfile, Address } from '../types';
import { db, isFirebaseConfigured } from '../firebase/config';
import { doc, getDoc, setDoc } from 'firebase/firestore';

const LOCAL_USER_KEY = 'sd_user_profile';

export const userRepository = {
  async getUserProfile(uid: string): Promise<UserProfile | null> {
    if (isFirebaseConfigured && db) {
      try {
        const snap = await getDoc(doc(db, 'users', uid));
        if (snap.exists()) {
          return snap.data() as UserProfile;
        }
      } catch (e) {
        console.warn('Firestore user fetch failed', e);
      }
    }
    const local = localStorage.getItem(LOCAL_USER_KEY);
    if (local) {
      try { return JSON.parse(local); } catch { /* Ignore malformed local profile data. */ }
    }
    return {
      uid,
      name: 'Mohit Jangde',
      email: 'mohit@example.com',
      phone: '+919876543210',
      role: 'admin',
      addresses: [
        {
          id: 'addr-1',
          name: 'Mohit Jangde',
          phone: '+919876543210',
          street: '12 Station Road, Near Main Market',
          city: 'Neemuch',
          state: 'Madhya Pradesh',
          pincode: '458441',
          isDefault: true,
          type: 'home'
        }
      ],
      referralCode: 'MOHIT100',
      walletBalance: 200,
      createdAt: new Date().toISOString()
    };
  },

  async saveUserProfile(profile: UserProfile): Promise<void> {
    localStorage.setItem(LOCAL_USER_KEY, JSON.stringify(profile));
    if (isFirebaseConfigured && db) {
      try {
        await setDoc(doc(db, 'users', profile.uid), profile);
      } catch (e) {
        console.warn('Firestore user save failed', e);
      }
    }
  }
};
