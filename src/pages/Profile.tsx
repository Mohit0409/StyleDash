import React, { useEffect, useState } from 'react';
import { Heart, LogOut, Package, Save } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { SEO } from '../components/SEO';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../services/authApi';
import { profileApi } from '../services/businessApi';
import { ApiError } from '../services/apiClient';

export const Profile: React.FC = () => {
  const { user, logout, refresh } = useAuth();
  const navigate = useNavigate();
  const address = user?.addresses?.find(item => item.isDefault) || user?.addresses?.[0];
  const [name, setName] = useState(user?.name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [street, setStreet] = useState(address?.street || '');
  const [city, setCity] = useState(address?.city || 'Neemuch');
  const [pincode, setPincode] = useState(address?.pincode || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setName(user.name); setPhone(user.phone || '');
    const saved = user.addresses?.find(item => item.isDefault) || user.addresses?.[0];
    if (saved) { setStreet(saved.street); setCity(saved.city); setPincode(saved.pincode); }
  }, [user]);

  const saveProfile = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try {
      await profileApi.update({
        name, phone,
        addresses: street || pincode ? [{ name, phone, street, city, state: 'Madhya Pradesh', pincode, type: 'home', isDefault: true }] : [],
      });
      await refresh(); setMessage('Profile and delivery address saved.');
    } catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Profile could not be saved.'); }
    finally { setSaving(false); }
  };

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try { await authApi.changePassword(currentPassword, newPassword); setCurrentPassword(''); setNewPassword(''); setMessage('Password changed and other sessions signed out.'); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : 'Password could not be changed.'); }
    finally { setSaving(false); }
  };

  return <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
    <SEO title="My Profile - StyleDash" />
    <div><h1 className="text-3xl font-black">My profile</h1><p className="text-sm text-neutral-500">Your account and saved delivery details are stored securely on the StyleDash server.</p></div>
    {error && <p className="text-sm text-red-600" role="alert">{error}</p>}{message && <p className="text-sm text-green-700" role="status">{message}</p>}
    <form onSubmit={saveProfile} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-4">
      <h2 className="text-xl font-black">Contact and delivery address</h2>
      <p className="text-xs text-neutral-500">Signed in as {user?.email || user?.phone}. Email changes require support.</p>
      <div className="grid sm:grid-cols-2 gap-4">
        <label className="text-xs font-bold">Full name<input required minLength={2} maxLength={80} value={name} onChange={event => setName(event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" /></label>
        <label className="text-xs font-bold">Phone<input required minLength={10} maxLength={20} value={phone} onChange={event => setPhone(event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" /></label>
        <label className="text-xs font-bold sm:col-span-2">Street address and landmark<input required minLength={5} maxLength={200} value={street} onChange={event => setStreet(event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" /></label>
        <label className="text-xs font-bold">City<input required minLength={2} maxLength={80} value={city} onChange={event => setCity(event.target.value)} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" /></label>
        <label className="text-xs font-bold">Pincode<input required pattern="[0-9]{6}" maxLength={6} inputMode="numeric" value={pincode} onChange={event => setPincode(event.target.value.replace(/\D/g, ''))} className="mt-1 w-full p-3 rounded-xl border dark:bg-neutral-800" /></label>
      </div>
      <button disabled={saving} className="flex items-center gap-2 bg-neutral-950 text-white dark:bg-lime-400 dark:text-black px-5 py-3 rounded-xl font-bold"><Save className="w-4" />Save profile</button>
    </form>
    {user?.hasPassword ? <form onSubmit={changePassword} className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-4">
      <h2 className="text-xl font-black">Change password</h2>
      <input required type="password" autoComplete="current-password" maxLength={256} value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} placeholder="Current password" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      <input required type="password" autoComplete="new-password" minLength={12} maxLength={256} value={newPassword} onChange={event => setNewPassword(event.target.value)} placeholder="New password (12+ characters)" className="w-full p-3 rounded-xl border dark:bg-neutral-800" />
      <button disabled={saving} className="px-5 py-3 rounded-xl border font-bold">Change password</button>
    </form> : <div className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border dark:border-neutral-800 space-y-2">
      <h2 className="text-xl font-black">Sign-in security</h2>
      <p className="text-sm text-neutral-500">This account uses a linked Google or mobile sign-in method and does not have a StyleDash password.</p>
    </div>}
    <div className="grid sm:grid-cols-2 gap-3">
      <Link to="/orders" className="flex gap-3 p-4 bg-white dark:bg-neutral-900 rounded-2xl border dark:border-neutral-800 font-bold"><Package className="w-4" />Order history</Link>
      <Link to="/wishlist" className="flex gap-3 p-4 bg-white dark:bg-neutral-900 rounded-2xl border dark:border-neutral-800 font-bold"><Heart className="w-4" />Saved wishlist</Link>
    </div>
    <button onClick={async () => { await logout(); navigate('/login'); }} className="w-full flex gap-3 p-4 rounded-2xl border text-red-600 font-bold"><LogOut className="w-4" />Logout</button>
  </div>;
};
