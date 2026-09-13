import React, { useState } from 'react';
import { CheckCircle2, LocateFixed, MapPin, TriangleAlert } from 'lucide-react';
import { serviceAreaRepository } from '../repositories/serviceAreaRepository';
import type { DeliveryCoordinates, ServiceArea } from '../types';

type CheckState = 'idle' | 'locating' | 'checking' | 'serviceable' | 'unserviceable' | 'error';

export interface DeliveryLocationCheckProps {
  pincode: string;
  coordinates?: DeliveryCoordinates | null;
  onCoordinates?: (coordinates: DeliveryCoordinates) => void;
  onResult?: (result: ServiceArea) => void;
}

const GEOLOCATION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 12_000,
  maximumAge: 60_000,
};

export const DeliveryLocationCheck: React.FC<DeliveryLocationCheckProps> = ({
  pincode,
  coordinates,
  onCoordinates,
  onResult,
}) => {
  const [state, setState] = useState<CheckState>('idle');
  const [message, setMessage] = useState('');

  const verify = async (nextCoordinates: DeliveryCoordinates) => {
    setState('checking');
    setMessage('Checking whether we deliver to this location...');
    try {
      const result = await serviceAreaRepository.checkLocation(pincode, nextCoordinates);
      onResult?.(result);
      if (result.serviceable) {
        setState('serviceable');
        setMessage(result.zoneName
          ? `Delivery is available in ${result.zoneName}.`
          : 'Delivery is available at this location.');
        return;
      }
      setState('unserviceable');
      setMessage('This location is outside Vibe4You\'s current delivery area.');
    } catch {
      setState('error');
      setMessage('We could not verify this location right now. Please try again.');
    }
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setState('error');
      setMessage('Location access is not available in this browser.');
      return;
    }
    setState('locating');
    setMessage('Getting your location...');
    navigator.geolocation.getCurrentPosition(
      position => {
        const nextCoordinates = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        };
        onCoordinates?.(nextCoordinates);
        void verify(nextCoordinates);
      },
      () => {
        setState('error');
        setMessage('Location permission is needed to confirm delivery availability.');
      },
      GEOLOCATION_OPTIONS,
    );
  };

  const busy = state === 'locating' || state === 'checking';
  const icon = state === 'serviceable'
    ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
    : state === 'unserviceable' || state === 'error'
      ? <TriangleAlert className="h-5 w-5 text-amber-600" />
      : <MapPin className="h-5 w-5 text-neutral-500" />;

  return (
    <section className="rounded-2xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-start gap-3">
        {icon}
        <div className="min-w-0 flex-1">
          <h3 className="font-black text-neutral-950 dark:text-white">Confirm delivery location</h3>
          <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-300">
            Vibe4You delivers only inside selected parts of Neemuch. Your location is used only to check delivery availability.
          </p>
          {message && (
            <p className="mt-2 text-sm font-semibold text-neutral-800 dark:text-neutral-100" role="status">
              {message}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={useCurrentLocation}
              className="inline-flex items-center gap-2 rounded-xl bg-neutral-950 px-4 py-2 text-sm font-black text-white disabled:opacity-50 dark:bg-lime-400 dark:text-neutral-950"
            >
              <LocateFixed className="h-4 w-4" />
              {state === 'locating' ? 'Getting location...' : 'Use my current location'}
            </button>
            {coordinates && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void verify(coordinates)}
                className="rounded-xl border border-neutral-300 px-4 py-2 text-sm font-black dark:border-neutral-700"
              >
                Check selected pin
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
