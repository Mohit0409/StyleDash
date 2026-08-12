import { ServiceArea } from '../types';

export const serviceAreaRepository = {
  async checkPincode(pincode: string): Promise<ServiceArea> {
    const supportedPincodes = ['458441', '458442', '458001', '458002'];
    const isServiceable = supportedPincodes.includes(pincode) || pincode.startsWith('458');
    return {
      pincode,
      city: 'Neemuch',
      state: 'Madhya Pradesh',
      serviceable: isServiceable,
      expressAvailable: isServiceable,
      estimatedDeliveryMinutes: 60
    };
  }
};
