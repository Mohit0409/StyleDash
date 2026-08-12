import { Order, OrderStatus } from '../types';
import { db, isFirebaseConfigured } from '../firebase/config';
import { collection, getDocs, doc, getDoc, setDoc, query, where, orderBy } from 'firebase/firestore';

const LOCAL_ORDERS_KEY = 'sd_orders';

export const orderRepository = {
  async getOrdersByUser(userId: string): Promise<Order[]> {
    if (isFirebaseConfigured && db) {
      try {
        const q = query(collection(db, 'orders'), where('userId', '==', userId));
        const snap = await getDocs(q);
        return snap.docs.map(d => ({ id: d.id, ...d.data() } as Order));
      } catch (e) {
        console.warn('Firestore orders fetch failed', e);
      }
    }
    const local = localStorage.getItem(LOCAL_ORDERS_KEY);
    if (local) {
      try {
        const orders: Order[] = JSON.parse(local);
        return orders.filter(o => o.userId === userId || userId === 'guest');
      } catch { /* Ignore malformed local order data. */ }
    }
    return [];
  },

  async getAllOrders(): Promise<Order[]> {
    if (isFirebaseConfigured && db) {
      try {
        const snap = await getDocs(collection(db, 'orders'));
        return snap.docs.map(d => ({ id: d.id, ...d.data() } as Order));
      } catch (e) {
        console.warn('Firestore all orders fetch failed', e);
      }
    }
    const local = localStorage.getItem(LOCAL_ORDERS_KEY);
    if (local) {
      try { return JSON.parse(local); } catch { /* Ignore malformed local order data. */ }
    }
    return [];
  },

  async getOrderById(orderId: string): Promise<Order | null> {
    const orders = await this.getAllOrders();
    return orders.find(o => o.id === orderId) || null;
  },

  async saveOrder(order: Order): Promise<void> {
    const orders = await this.getAllOrders();
    const idx = orders.findIndex(o => o.id === order.id);
    if (idx >= 0) {
      orders[idx] = order;
    } else {
      orders.unshift(order);
    }
    localStorage.setItem(LOCAL_ORDERS_KEY, JSON.stringify(orders));

    if (isFirebaseConfigured && db) {
      try {
        await setDoc(doc(db, 'orders', order.id), order);
      } catch (e) {
        console.warn('Firestore order save failed', e);
      }
    }
  },

  async updateOrderStatus(orderId: string, status: OrderStatus, note?: string): Promise<void> {
    const order = await this.getOrderById(orderId);
    if (order) {
      order.status = status;
      order.updatedAt = new Date().toISOString();
      order.statusHistory.push({
        status,
        timestamp: new Date().toISOString(),
        note: note || undefined,
      });
      await this.saveOrder(order);
    }
  }
};
