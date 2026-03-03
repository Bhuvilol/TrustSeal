import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getShipmentById, getShipments } from '@/api/shipments';
import type { ShipmentWithDetails } from '@/types';
import { getErrorMessage } from '@/utils/errors';
import StatusBadge from '@/components/StatusBadge';

function QRLookupPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<ShipmentWithDetails | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleLookup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      setErrorMessage('Enter shipment ID or shipment code.');
      return;
    }

    setIsSearching(true);
    setErrorMessage(null);
    setResult(null);

    try {
      try {
        const shipmentById = await getShipmentById(normalized);
        setResult(shipmentById);
        return;
      } catch {
        const shipments = await getShipments({ limit: 200 });
        const matched = shipments.find(
          (shipment) =>
            shipment.shipment_code.toLowerCase() === normalized.toLowerCase() ||
            shipment.id.toLowerCase() === normalized.toLowerCase(),
        );

        if (!matched) {
          setErrorMessage('Shipment not found for this QR value.');
          return;
        }

        const fullShipment = await getShipmentById(matched.id);
        setResult(fullShipment);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error, 'Lookup failed'));
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="panel p-6">
        <h1 className="text-2xl font-semibold text-slate-100">QR Shipment Lookup</h1>
        <p className="mt-2 text-sm text-slate-400">
          Paste a scanned QR payload (shipment ID or shipment code) to open the shipment dashboard.
        </p>

        <form className="mt-5 flex flex-col gap-3 md:flex-row" onSubmit={handleLookup}>
          <input
            type="text"
            className="input-field md:flex-1"
            placeholder="e.g. SHIP-2026-0009 or shipment UUID"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" className="btn-primary md:min-w-32" disabled={isSearching}>
            {isSearching ? 'Searching...' : 'Lookup'}
          </button>
        </form>

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-status-red/35 bg-status-red/10 px-3 py-2 text-sm text-status-red">
            {errorMessage}
          </p>
        )}
      </section>

      {result && (
        <section className="panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Matched Shipment</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-100">{result.shipment_code}</h2>
              <p className="mt-2 text-sm text-slate-300">
                {result.origin} {'->'} {result.destination}
              </p>
            </div>
            <StatusBadge kind="shipment" status={result.status} />
          </div>

          <button
            type="button"
            className="btn-primary mt-5"
            onClick={() => navigate(`/shipments/${result.id}`)}
          >
            Open Shipment Dashboard
          </button>
        </section>
      )}
    </div>
  );
}

export default QRLookupPage;
