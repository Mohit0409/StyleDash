export const isExpressDeliveryAvailable = (date = new Date()): boolean => {
  const weekday = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Kolkata',
    weekday: 'short',
  }).format(date);
  return weekday === 'Sat' || weekday === 'Sun';
};

export const deliveryAvailabilityMessage = (date = new Date()): string =>
  isExpressDeliveryAvailable(date)
    ? 'Normal within-a-day delivery is selected. Weekend express delivery is also available.'
    : 'Normal within-a-day delivery is selected. Express delivery is disabled Monday–Friday.';
