import React, { useEffect, useMemo, useState } from 'react';
import { BarChart3, Boxes, CheckCircle2, Clock3, Package, ShoppingBag, Store } from 'lucide-react';
import { SellerProducts } from './SellerProducts';
import { SellerOrders } from './SellerOrders';
import { ApiError } from '../services/apiClient';
import {
  type SellerOrder,
  type SellerProduct,
  type ShopApplication,
  sellerOrderApi,
  shopProductApi,
} from '../services/businessApi';

type DashboardTab = 'overview' | 'shop' | 'products' | 'orders';

const messageForError = (cause: unknown) =>
  cause instanceof ApiError || cause instanceof Error
    ? cause.message
    : 'Seller dashboard could not be loaded.';

export const SellerDashboard: React.FC<{ application: ShopApplication }> = ({ application }) => {
  const [tab, setTab] = useState<DashboardTab>('overview');
  const [products, setProducts] = useState<SellerProduct[]>([]);
  const [orders, setOrders] = useState<SellerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([shopProductApi.mine(), sellerOrderApi.mine()])
      .then(([productResult, orderResult]) => { if (active) { setProducts(productResult); setOrders(orderResult); } })
      .catch(cause => { if (active) setError(messageForError(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const metrics = useMemo(() => {
    const pending = products.filter(product => ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED'].includes(product.status)).length;
    const published = products.filter(product => product.status === 'PUBLISHED').length;
    const drafts = products.filter(product => ['DRAFT', 'REJECTED'].includes(product.status)).length;
    const inventory = products.reduce((sum, product) => sum + product.inventory, 0);
    return { total: products.length, pending, published, drafts, inventory, orders: orders.length };
  }, [products, orders]);

  const tabs: Array<{ id: DashboardTab; label: string; icon: React.ReactNode }> = [
    { id: 'overview', label: 'Overview', icon: <BarChart3 className="w-4" /> },
    { id: 'shop', label: 'My Shop', icon: <Store className="w-4" /> },
    { id: 'products', label: 'Products', icon: <Boxes className="w-4" /> },
    { id: 'orders', label: 'Orders', icon: <ShoppingBag className="w-4" /> },
  ];

  return <section className="space-y-6" aria-labelledby="seller-dashboard-title">
    <div className="rounded-3xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-lime-700">Seller workspace</p>
          <h2 id="seller-dashboard-title" className="mt-1 text-2xl font-black">Seller Dashboard</h2>
          <p className="mt-1 text-sm text-neutral-500">Manage your shop and product submissions without administrator privileges.</p>
        </div>
        <div className="rounded-2xl bg-neutral-950 px-4 py-3 text-white dark:bg-lime-400 dark:text-neutral-950">
          <p className="text-[10px] font-black uppercase tracking-wider">Shop status</p>
          <p className="font-black">{application.status.replace('_', ' ')}</p>
        </div>
      </div>
      <div className="mt-5 flex gap-2 overflow-x-auto" role="tablist" aria-label="Seller dashboard sections">
        {tabs.map(item => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} onClick={() => setTab(item.id)} className={`flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold ${tab === item.id ? 'bg-neutral-950 text-white dark:bg-lime-400 dark:text-neutral-950' : 'border border-neutral-200 dark:border-neutral-700'}`}>{item.icon}{item.label}</button>)}
      </div>
    </div>

    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {tab === 'overview' && <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Metric label="Total products" value={loading ? '…' : metrics.total} icon={<Package className="w-5" />} />
        <Metric label="Pending review" value={loading ? '…' : metrics.pending} icon={<Clock3 className="w-5" />} />
        <Metric label="Published" value={loading ? '…' : metrics.published} icon={<CheckCircle2 className="w-5" />} />
        <Metric label="Draft / changes" value={loading ? '…' : metrics.drafts} icon={<Boxes className="w-5" />} />
        <Metric label="Submitted stock" value={loading ? '…' : metrics.inventory} icon={<BarChart3 className="w-5" />} />
        <Metric label="Seller orders" value={loading ? '…' : metrics.orders} icon={<ShoppingBag className="w-5" />} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
          <p className="text-xs font-black uppercase tracking-wider text-neutral-500">Your shop</p>
          <h3 className="mt-1 text-xl font-black">{application.shopName}</h3>
          <p className="mt-2 text-sm text-neutral-500">{application.description}</p>
          <button type="button" onClick={() => setTab('shop')} className="mt-4 rounded-xl border px-4 py-2 text-sm font-bold">View shop details</button>
        </article>
        <article className="rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
          <p className="text-xs font-black uppercase tracking-wider text-neutral-500">Next action</p>
          <h3 className="mt-1 text-xl font-black">{metrics.drafts ? 'Finish your product drafts' : metrics.pending ? 'Products are under review' : 'Add your next product'}</h3>
          <p className="mt-2 text-sm text-neutral-500">Only StyleDash administrators can approve or publish products. You control preparation and submission only.</p>
          <button type="button" onClick={() => setTab('products')} className="mt-4 rounded-xl bg-neutral-950 px-4 py-2 text-sm font-bold text-white dark:bg-lime-400 dark:text-neutral-950">Manage products</button>
        </article>
      </div>
    </div>}

    {tab === 'shop' && <article className="rounded-3xl border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-start gap-3"><Store className="mt-1 w-6 text-lime-600" /><div><h3 className="text-xl font-black">My Shop</h3><p className="text-sm text-neutral-500">Approved information currently stored for this seller account.</p></div></div>
      <dl className="mt-6 grid gap-5 sm:grid-cols-2">
        <Detail label="Shop name" value={application.shopName} />
        <Detail label="Owner / contact" value={application.ownerName} />
        <Detail label="Category" value={application.category} />
        <Detail label="Registered contact" value={application.registeredMobile || application.registeredEmail || 'Not available'} />
        <Detail label="Address" value={`${application.address}, ${application.city}, ${application.state} ${application.pincode}`} wide />
        <Detail label="Description" value={application.description} wide />
        {application.businessInformation && <Detail label="Business information" value={application.businessInformation} wide />}
      </dl>
      <p className="mt-5 rounded-2xl bg-neutral-50 p-4 text-xs text-neutral-500 dark:bg-neutral-800">Shop identity and approval status remain administrator-controlled. Editable seller settings can be added here in a later dashboard phase.</p>
    </article>}

    {tab === 'products' && <SellerProducts initialProducts={products} onProductsChange={setProducts} />}
    {tab === 'orders' && <SellerOrders orders={orders} loading={loading} />}
  </section>;
};

const Metric: React.FC<{ label: string; value: number | string; icon: React.ReactNode }> = ({ label, value, icon }) => (
  <article className="rounded-2xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div className="flex items-center justify-between gap-3 text-neutral-500">
      <p className="text-xs font-bold">{label}</p>
      {icon}
    </div>
    <p className="mt-2 text-2xl font-black">{value}</p>
  </article>
);

const Detail: React.FC<{ label: string; value: string; wide?: boolean }> = ({ label, value, wide }) => (
  <div className={wide ? 'sm:col-span-2' : undefined}>
    <dt className="text-xs font-black uppercase tracking-wider text-neutral-500">{label}</dt>
    <dd className="mt-1 text-sm font-semibold">{value}</dd>
  </div>
);
