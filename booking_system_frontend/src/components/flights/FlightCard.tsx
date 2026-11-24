import type { Flight } from '../../types';
import { Card, Button } from '../common';
import { Plane, Clock, Users } from 'lucide-react';
import { formatCurrency, formatDate, formatTime, calculateDuration, formatSeatClass } from '../../utils/formatters';
import { motion } from 'framer-motion';

interface FlightCardProps {
  flight: Flight;
  onBook: (flight: Flight) => void;
}

export const FlightCard = ({ flight, onBook }: FlightCardProps) => {
  // Whole flight is sold out only when every class is sold out
  const isSoldOut = flight.seats_available === 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.3 }}
    >
      <Card className="h-full flex flex-col">
        {/* Route Header */}
        <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
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
        </div>

        {/* Flight Details */}
        <div className="space-y-3 mb-6 flex-1">
          {/* Departure & Arrival */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-star-white/60 mb-1">Departure</p>
              <p className="text-sm font-medium text-star-white">
                {formatDate(flight.departure_time, 'MMM dd, yyyy')}
              </p>
              <p className="text-lg font-bold text-cosmic-purple">
                {formatTime(flight.departure_time)}
              </p>
            </div>
            <div>
              <p className="text-xs text-star-white/60 mb-1">Arrival</p>
              <p className="text-sm font-medium text-star-white">
                {formatDate(flight.arrival_time, 'MMM dd, yyyy')}
              </p>
              <p className="text-lg font-bold text-cosmic-purple">
                {formatTime(flight.arrival_time)}
              </p>
            </div>
          </div>

          {/* Duration */}
          <div className="flex items-center gap-2 text-star-white/70">
            <Clock size={16} />
            <span className="text-sm">
              Duration: {calculateDuration(flight.departure_time, flight.arrival_time)}
            </span>
          </div>

          {/* Price & Seats per Class */}
          <div className="space-y-2">
            {flight.seat_classes.map((seatClass) => {
              const classSoldOut = seatClass.seats_available === 0;
              const classLowSeats = seatClass.seats_available <= 2;
              return (
                <div
                  key={seatClass.seat_class}
                  className="flex items-center justify-between gap-3"
                >
                  <div>
                    <p className="text-sm font-medium text-star-white">
                      {formatSeatClass(seatClass.seat_class)}
                    </p>
                    <div className="flex items-center gap-1">
                      <Users size={14} className={classLowSeats ? 'text-solar-orange' : 'text-star-white/70'} />
                      <span className={`text-xs ${classLowSeats ? 'text-solar-orange font-semibold' : 'text-star-white/70'}`}>
                        {classSoldOut ? 'Sold Out' : `${seatClass.seats_available} seats available`}
                      </span>
                    </div>
                  </div>
                  <span className={`text-lg font-bold ${classSoldOut ? 'text-star-white/40' : 'text-star-white'}`}>
                    {formatCurrency(seatClass.price)}
                  </span>
                </div>
              );
            })}
            <p className="text-xs text-star-white/60">per seat</p>
          </div>
        </div>

        {/* Book Button */}
        <Button
          onClick={() => onBook(flight)}
          disabled={isSoldOut}
          className="w-full"
        >
          {isSoldOut ? 'Sold Out' : 'Book Now'}
        </Button>
      </Card>
    </motion.div>
  );
};

// Made with Bob
