import { Vendor } from '../types';
import { VENDORS } from '../data/vendors';

export const vendorRepository = {
  async getVendors(): Promise<Vendor[]> {
    return VENDORS;
  }
};
