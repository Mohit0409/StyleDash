import React, { useEffect, useState } from 'react';
import { Globe2, Save, Truck } from 'lucide-react';
import { ApiError } from '../services/apiClient';
import { type ShopApplication, vendorApplicationApi } from '../services/businessApi';
import { useToast } from '../context/ToastContext';

interface Props {
  application: ShopApplication;
  onChange: (application: ShopApplication) => void;
}

export const ShopDeliverySettings: React.FC<Props> = ({ application, onChange }) => {
  const { showToast } = useToast();
  const [enabled, setEnabled] = useState(application.allIndiaDeliveryEnabled === true);
  const [shippingPayer, setShippingPayer] = useState<'shop' | 'customer'>(
    application.allIndiaShippingPayer === 'shop' ? 'shop' : 'customer',
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setEnabled(application.allIndiaDeliveryEnabled === true);
    setShippingPayer(application.allIndiaShippingPayer === 'shop' ? 'shop' : 'customer');
  }, [application.allIndiaDeliveryEnabled, application.allIndiaShippingPayer]);

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const updated = await vendorApplicationApi.updateDeliverySettings({
        allIndiaDeliveryEnabled: enabled,
        allIndiaShippingPayer: shippingPayer,
      });
      onChange(updated);
      showToast('All India delivery settings saved.', 'success');
    } catch (cause) {
      setError(cause instanceof ApiError || cause instanceof Error
        ? cause.message
        : 'Delivery settings could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900 space-y-5">
      <div className="flex items-start gap-3">
        <div className="rounded-2xl bg-lime-100 p-3 text-lime-800 dark:bg-lime-950/40 dark:text-lime-300">
          <Globe2 className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-black">All India delivery</h2>
          <p className="mt-1 text-xs leading-relaxed text-neutral-500">
            Optional mediator feature. Vibe4You only takes the customer&apos;s order request and informs your shop.
            Your shop handles payment, courier booking, shipping and customer coordination directly.
          </p>
        </div>
      </div>

      <label className="flex items-start gap-3 rounded-2xl border border-neutral-200 p-4 dark:border-neutral-800">
        <input
          type="checkbox"
          checked={enabled}
          onChange={event => setEnabled(event.target.checked)}
          className="mt-1 accent-lime-500"
        />
        <span>
          <span className="block text-sm font-black">Accept All India order requests</span>
          <span className="mt-1 block text-xs text-neutral-500">
            Existing Neemuch delivery and payment options are unchanged.
          </span>
        </span>
      </label>

      <fieldset disabled={!enabled} className="space-y-3 disabled:opacity-50">
        <legend className="text-sm font-black">Who pays the courier / delivery charge?</legend>
        <label className="flex items-start gap-3 rounded-2xl border p-4 dark:border-neutral-800">
          <input
            type="radio"
            name="all-india-shipping-payer"
            checked={shippingPayer === 'shop'}
            onChange={() => setShippingPayer('shop')}
            className="mt-1 accent-lime-500"
          />
          <span><strong className="block text-sm">Shop pays</strong><span className="text-xs text-neutral-500">Customer is not asked to pay a separate shipping charge.</span></span>
        </label>
        <label className="flex items-start gap-3 rounded-2xl border p-4 dark:border-neutral-800">
          <input
            type="radio"
            name="all-india-shipping-payer"
            checked={shippingPayer === 'customer'}
            onChange={() => setShippingPayer('customer')}
            className="mt-1 accent-lime-500"
          />
          <span><strong className="block text-sm">Customer pays</strong><span className="text-xs text-neutral-500">Your shop confirms the courier charge directly with the customer before shipping.</span></span>
        </label>
      </fieldset>

      <div className="rounded-2xl bg-amber-50 p-4 text-xs leading-relaxed text-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
        <div className="flex gap-2 font-bold"><Truck className="h-4 w-4 shrink-0" />Important</div>
        <p className="mt-1">For these orders, Vibe4You does not collect product payment or shipping charges and does not perform delivery. The order request will appear in your shop portal and, when email is available, a notification is sent to your registered shop email.</p>
      </div>

      {error && <p role="alert" className="text-sm font-semibold text-red-600">{error}</p>}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="flex items-center gap-2 rounded-xl bg-neutral-950 px-5 py-3 text-sm font-black text-white disabled:opacity-50 dark:bg-lime-400 dark:text-neutral-950"
        >
          <Save className="h-4 w-4" />{saving ? 'Saving…' : 'Save delivery settings'}
        </button>
      </div>
    </section>
  );
};
