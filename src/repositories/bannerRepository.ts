import { AdSlot } from '../types';
import { BANNERS } from '../data/banners';

export const bannerRepository = {
  async getBanners(): Promise<AdSlot[]> {
    return BANNERS;
  }
};
