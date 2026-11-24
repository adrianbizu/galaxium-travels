import { useEffect, useState } from 'react';
import type { Flight, SeatClass } from '../../types';
import { Modal, Button } from '../common';
import { Plane, Calendar, Clock, DollarSign, Check } from 'lucide-react';
import { formatCurrency, formatDate, calculateDuration, formatSeatClass } from '../../utils/formatters';
import { bookFlight, isErrorResponse } from '../../services/api';
import { useUser } from '../../hooks/useUser';
import toast from 'react-hot-toast';

interface BookingModalProps {
  isOpen: boolean;
  onClose: () => void;
  flight: Flight | null;
  onSuccess: () => void;
}

export const BookingModal = ({ isOpen, onClose, flight, onSuccess }: BookingModalProps) => {
  const { user } = useUser();
  const [isLoading, setIsLoading] = useState(false);
  const [selectedClass, setSelectedClass] = useState<SeatClass>('economy');

  // Default to the cheapest class that still has seats whenever the modal opens or the flight changes
  useEffect(() => {
    if (!flight) return;
    const available = flight.seat_classes.filter((c) => c.seats_available > 0);
    if (available.length > 0) {
      setSelectedClass(available.reduce((a, b) => (b.price < a.price ? b : a)).seat_class);
    }
  }, [flight, isOpen]);

  if (!flight) return null;

  const selectedPrice =
    flight.seat_classes.find((c) => c.seat_class === selectedClass)?.price ?? flight.price;

  const handleConfirmBooking = async () => {
    if (!user) {
      toast.error('Please sign in to book a flight');
      return;
    }

    setIsLoading(true);

    try {
      const result = await bookFlight({
        user_id: user.user_id,
        name: user.name,
        flight_id: flight.flight_id,
        seat_class: selectedClass,
      });

      if (isErrorResponse(result)) {
        toast.error(result.details || result.error);
        return;
      }

      toast.success('Flight booked successfully!');
      onSuccess();
      onClose();
    } catch (error: any) {
      toast.error(error.details || error.error || 'Failed to book flight');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Confirm Your Booking"
      size="md"
    >
      <div className="space-y-6">
        {/* Flight Summary */}
        <div className="glass-card p-4 bg-white/5">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-cosmic-gradient">
              <Plane className="text-white" size={24} />
            </div>
            <div>
              <h3 className="text-xl font-bold text-star-white">
                {flight.origin} → {flight.destination}
              </h3>
              <p className="text-sm text-star-white/60">
                Flight #{flight.flight_id}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {/* Departure */}
            <div className="flex items-start gap-3">
              <Calendar className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Departure</p>
                <p className="text-star-white font-medium">
                  {formatDate(flight.departure_time)}
                </p>
              </div>
            </div>

            {/* Arrival */}
            <div className="flex items-start gap-3">
              <Calendar className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Arrival</p>
                <p className="text-star-white font-medium">
                  {formatDate(flight.arrival_time)}
                </p>
              </div>
            </div>

            {/* Duration */}
            <div className="flex items-start gap-3">
              <Clock className="text-cosmic-purple mt-1" size={20} />
              <div>
                <p className="text-xs text-star-white/60">Duration</p>
                <p className="text-star-white font-medium">
                  {calculateDuration(flight.departure_time, flight.arrival_time)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Seat Class */}
        <fieldset disabled={isLoading}>
          <legend className="block text-sm font-medium text-star-white mb-2">
            Seat Class
          </legend>
          <div className="space-y-2" role="radiogroup" aria-label="Seat class">
            {flight.seat_classes.map((c) => {
              const soldOut = c.seats_available === 0;
              const selected = selectedClass === c.seat_class;
              return (
                <label
                  key={c.seat_class}
                  className={`flex items-center gap-3 rounded-lg border px-4 py-3 transition-all duration-200 focus-within:ring-2 focus-within:ring-cosmic-purple ${
                    soldOut
                      ? 'cursor-not-allowed border-white/10 bg-white/5 opacity-50'
                      : selected
                        ? 'cursor-pointer border-cosmic-purple bg-cosmic-purple/20'
                        : 'cursor-pointer border-white/10 bg-white/5 hover:border-cosmic-purple/60 hover:bg-white/10'
                  }`}
                >
                  <input
                    type="radio"
                    name="seat-class"
                    value={c.seat_class}
                    checked={selected}
                    disabled={soldOut}
                    onChange={() => setSelectedClass(c.seat_class)}
                    className="sr-only"
                  />
                  <span
                    aria-hidden="true"
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors duration-200 ${
                      selected ? 'border-cosmic-purple bg-cosmic-purple' : 'border-white/30 bg-transparent'
                    }`}
                  >
                    {selected && <Check size={14} className="text-white" />}
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-medium text-star-white">
                      {formatSeatClass(c.seat_class)}
                    </span>
                    <span className="block text-xs text-star-white/60">
                      {soldOut ? 'Sold out' : `${c.seats_available} left`}
                    </span>
                  </span>
                  <span className="text-lg font-bold text-star-white">
                    {formatCurrency(c.price)}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {/* Passenger Info */}
        {user && (
          <div className="glass-card p-4 bg-white/5">
            <h4 className="text-sm font-semibold text-star-white mb-2">
              Passenger Information
            </h4>
            <p className="text-star-white">{user.name}</p>
            <p className="text-star-white/60 text-sm">{user.email}</p>
          </div>
        )}

        {/* Price */}
        <div className="flex items-center justify-between p-4 glass-card bg-cosmic-gradient">
          <div className="flex items-center gap-2">
            <DollarSign className="text-white" size={24} />
            <span className="text-white font-semibold">Total Price</span>
          </div>
          <span className="text-2xl font-bold text-white">
            {formatCurrency(selectedPrice)}
          </span>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirmBooking}
            isLoading={isLoading}
            className="flex-1"
          >
            Confirm Booking
          </Button>
        </div>

        <p className="text-xs text-star-white/60 text-center">
          By confirming, you agree to our terms and conditions
        </p>
      </div>
    </Modal>
  );
};

// Made with Bob
