import type { CustodyCheckpoint } from '@/types';
import { formatDateTime } from '@/utils/format';

interface CustodyTableProps {
  checkpoints: CustodyCheckpoint[];
}

function CustodyTable({ checkpoints }: CustodyTableProps) {
  return (
    <section className="panel p-5">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-slate-100">Custody Checkpoints</h3>
        <p className="mt-1 text-sm text-slate-400">Biometric and blockchain verification records.</p>
      </div>

      {checkpoints.length === 0 ? (
        <p className="rounded-xl border border-slate-700 bg-surface-800/70 px-3 py-2 text-sm text-slate-400">
          No custody checkpoints recorded.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full table-auto border-collapse text-left text-sm">
            <thead className="border-b border-slate-700 text-xs uppercase tracking-[0.12em] text-slate-400">
              <tr>
                <th className="px-3 py-2 font-medium">Verified By</th>
                <th className="px-3 py-2 font-medium">Biometric</th>
                <th className="px-3 py-2 font-medium">Blockchain TX</th>
                <th className="px-3 py-2 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {checkpoints.map((checkpoint) => (
                <tr key={checkpoint.id} className="border-b border-slate-700/50 text-slate-200">
                  <td className="px-3 py-3">{checkpoint.verified_by ?? 'N/A'}</td>
                  <td className="px-3 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        checkpoint.biometric_verified
                          ? 'bg-status-green/20 text-status-green'
                          : 'bg-status-red/20 text-status-red'
                      }`}
                    >
                      {checkpoint.biometric_verified ? 'Verified' : 'Not Verified'}
                    </span>
                  </td>
                  <td className="max-w-[240px] truncate px-3 py-3 font-mono text-xs text-slate-300">
                    {checkpoint.blockchain_tx_hash ?? 'N/A'}
                  </td>
                  <td className="px-3 py-3 text-slate-300">{formatDateTime(checkpoint.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default CustodyTable;

