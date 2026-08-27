import React, { useMemo } from 'react';
import { CircleDollarSign, Clock3, ShieldCheck, WalletCards } from 'lucide-react';
import type { SellerSettlement } from '../services/businessApi';

const money = (paise: number | null | undefined) =>
  paise == null ? '—' : `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

const label = (value: string) => value.replace(/_/g, ' ');

const statusMessage: Record<SellerSettlement['status'], string> = {
  COMMISSION_REQUIRED: 'StyleDash commission is not configured yet.',
  AWAITING_PAYMENT: 'Waiting for confirmed online payment.',
  AWAITING_COLLECTION: 'Delivered COD order; cash collection still needs private-admin confirmation.',
  PENDING_CLEARANCE: 'Delivery completed. Waiting for the customer support window to close.',
  ON_HOLD: 'Settlement is paused while a return, cancellation, refund, or review is active.',
  ELIGIBLE: 'Cleared for manual payout processing by StyleDash admin.',
  SETTLED: 'StyleDash admin recorded this payout as completed externally.',
  VOID: 'This settlement was voided and must not be paid.',
};

export const SellerEarnings: React.FC<{ settlements: SellerSettlement[]; loading: boolean }> = ({ settlements, loading }) => {
  const totals = useMemo(() => settlements.reduce((sum, row) => {
    if (row.status !== 'VOID') {
      sum.gross += row.grossAmountPaise || 0;
      sum.commission += row.commissionAmountPaise || 0;
      sum.net += row.netAmountPaise || 0;
    }
    if (row.status === 'SETTLED') sum.settled += row.netAmountPaise || 0;
    if (row.status === 'ELIGIBLE') sum.eligible += row.netAmountPaise || 0;
    return sum;
  }, { gross: 0, commission: 0, net: 0, settled: 0, eligible: 0 }), [settlements]);

  if (loading) return <p className="text-sm text-neutral-500">Loading earnings…</p>;

  return <div className="space-y-5">
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Metric label="Gross delivered" value={money(totals.gross)} icon={<CircleDollarSign className="w-5" />} />
      <Metric label="StyleDash commission" value={money(totals.commission)} icon={<ShieldCheck className="w-5" />} />
      <Metric label="Seller net" value={money(totals.net)} icon={<WalletCards className="w-5" />} />
      <Metric label="Eligible now" value={money(totals.eligible)} icon={<Clock3 className="w-5" />} />
      <Metric label="Recorded paid" value={money(totals.settled)} icon={<ShieldCheck className="w-5" />} />
    </div>

    <article className="rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-wider text-neutral-500">Settlement ledger</p>
          <h3 className="mt-1 text-xl font-black">Earnings & payouts</h3>
        </div>
        <p className="max-w-xl text-xs text-neutral-500">Amounts are server-calculated snapshots. Only StyleDash private admin can confirm COD collection, release a settlement, or record an external payout.</p>
      </div>
      <div className="mt-5 space-y-3">
        {settlements.length === 0 && <p className="rounded-2xl bg-neutral-50 p-4 text-sm text-neutral-500 dark:bg-neutral-800">No delivered seller segments have created a settlement yet.</p>}
        {settlements.map(row => <section key={row.id} className="rounded-2xl border border-neutral-200 p-4 dark:border-neutral-700">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-wider text-neutral-500">Order {row.orderId}</p>
              <h4 className="mt-1 font-black">{label(row.status)}</h4>
              <p className="mt-1 text-xs text-neutral-500">{statusMessage[row.status]}</p>
            </div>
            <div className="text-left sm:text-right">
              <p className="text-xs text-neutral-500">Seller net</p>
              <p className="text-xl font-black">{money(row.netAmountPaise)}</p>
            </div>
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Detail label="Gross" value={money(row.grossAmountPaise)} />
            <Detail label={`Commission${row.commissionPercent == null ? '' : ` (${row.commissionPercent}%)`}`} value={money(row.commissionAmountPaise)} />
            <Detail label="Payment" value={row.paymentMethod.toUpperCase()} />
            <Detail label="Clearance" value={new Date(row.clearanceUntil).toLocaleString()} />
          </dl>
          {row.holdReason && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">Hold: {row.holdReason}</p>}
          {row.payoutReference && <p className="mt-3 text-xs text-neutral-500">External payout reference: <strong>{row.payoutReference}</strong></p>}
        </section>)}
      </div>
    </article>
  </div>;
};

const Metric: React.FC<{ label: string; value: string; icon: React.ReactNode }> = ({ label, value, icon }) => (
  <article className="rounded-2xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div className="flex items-center justify-between gap-3 text-neutral-500">
      <p className="text-xs font-bold">{label}</p>
      {icon}
    </div>
    <p className="mt-2 text-xl font-black">{value}</p>
  </article>
);

const Detail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <dt className="text-[10px] font-black uppercase tracking-wider text-neutral-500">{label}</dt>
    <dd className="mt-1 font-semibold">{value}</dd>
  </div>
);
