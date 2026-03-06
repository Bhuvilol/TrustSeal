import { ExternalLink, CheckCircle, Clock, XCircle, AlertCircle, FileText, Link as LinkIcon } from 'lucide-react';
import type { ShipmentLatestProof } from '@/types';
import { formatDateTime } from '@/utils/format';

interface ProofPanelProps {
  proof: ShipmentLatestProof;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

function ProofPanel({ proof, onRefresh, isRefreshing = false }: ProofPanelProps) {
  const getStatusIcon = (status: string | null) => {
    switch (status) {
      case 'anchored':
      case 'confirmed':
      case 'pinned':
        return <CheckCircle className="h-5 w-5 text-green-400" />;
      case 'pending':
      case 'submitted':
      case 'ipfs_pinned':
      case 'custody_verified':
      case 'anchor_pending':
        return <Clock className="h-5 w-5 text-yellow-400" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-400" />;
      default:
        return <AlertCircle className="h-5 w-5 text-slate-400" />;
    }
  };

  const getStatusColor = (status: string | null) => {
    switch (status) {
      case 'anchored':
      case 'confirmed':
      case 'pinned':
        return 'text-green-400';
      case 'pending':
      case 'submitted':
      case 'ipfs_pinned':
      case 'custody_verified':
      case 'anchor_pending':
        return 'text-yellow-400';
      case 'failed':
        return 'text-red-400';
      default:
        return 'text-slate-400';
    }
  };

  const formatStatus = (status: string | null) => {
    if (!status) return 'Unknown';
    return status
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const ipfsCid = proof.ipfs.cid;
  const txHash = proof.chain.tx_hash;
  const network = proof.chain.network || 'polygon-amoy';

  const getExplorerUrl = (hash: string) => {
    if (network.includes('amoy')) {
      return `https://amoy.polygonscan.com/tx/${hash}`;
    }
    return `https://polygonscan.com/tx/${hash}`;
  };

  return (
    <div className="panel p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-brand-400" />
          <h2 className="text-lg font-semibold text-slate-100">Proof & Chain Anchor</h2>
        </div>
        {onRefresh && (
          <button
            type="button"
            className="btn-secondary px-3 py-2 text-xs"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Bundle Overview */}
        <div className="rounded-lg border border-slate-700/70 bg-surface-800/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">Bundle Information</h3>
            <div className="flex items-center gap-2">
              {getStatusIcon(proof.status)}
              <span className={`text-sm font-medium ${getStatusColor(proof.status)}`}>
                {formatStatus(proof.status)}
              </span>
            </div>
          </div>
          <div className="grid gap-2 text-sm text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Bundle ID:</span>
              <span className="font-mono text-xs">{proof.bundle_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Epoch:</span>
              <span>{proof.epoch}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Record Count:</span>
              <span>{proof.record_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Created:</span>
              <span>{formatDateTime(proof.created_at)}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-slate-400">Batch Hash:</span>
              <span className="break-all font-mono text-xs text-slate-300">{proof.batch_hash}</span>
            </div>
          </div>
        </div>

        {/* IPFS Storage */}
        <div className="rounded-lg border border-slate-700/70 bg-surface-800/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">IPFS Storage</h3>
            <div className="flex items-center gap-2">
              {getStatusIcon(proof.ipfs.pin_status)}
              <span className={`text-sm font-medium ${getStatusColor(proof.ipfs.pin_status)}`}>
                {formatStatus(proof.ipfs.pin_status)}
              </span>
            </div>
          </div>
          <div className="space-y-2 text-sm text-slate-300">
            {ipfsCid ? (
              <>
                <div className="flex flex-col gap-1">
                  <span className="text-slate-400">Content ID (CID):</span>
                  <span className="break-all font-mono text-xs text-slate-300">{ipfsCid}</span>
                </div>
                {proof.ipfs.content_hash && (
                  <div className="flex flex-col gap-1">
                    <span className="text-slate-400">Content Hash:</span>
                    <span className="break-all font-mono text-xs text-slate-300">{proof.ipfs.content_hash}</span>
                  </div>
                )}
                {proof.ipfs.size_bytes && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Size:</span>
                    <span>{(proof.ipfs.size_bytes / 1024).toFixed(2)} KB</span>
                  </div>
                )}
                {proof.ipfs.pinned_at && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Pinned:</span>
                    <span>{formatDateTime(proof.ipfs.pinned_at)}</span>
                  </div>
                )}
                <a
                  href={`https://ipfs.io/ipfs/${ipfsCid}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-2 rounded-lg bg-brand-500/20 px-3 py-2 text-sm font-medium text-brand-300 transition hover:bg-brand-500/30 hover:text-brand-200"
                >
                  <LinkIcon className="h-4 w-4" />
                  View on IPFS Gateway
                  <ExternalLink className="h-3 w-3" />
                </a>
              </>
            ) : (
              <p className="text-slate-400">IPFS content not yet available</p>
            )}
          </div>
        </div>

        {/* Blockchain Anchor */}
        <div className="rounded-lg border border-slate-700/70 bg-surface-800/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-200">Blockchain Anchor</h3>
            <div className="flex items-center gap-2">
              {getStatusIcon(proof.chain.anchor_status)}
              <span className={`text-sm font-medium ${getStatusColor(proof.chain.anchor_status)}`}>
                {formatStatus(proof.chain.anchor_status)}
              </span>
            </div>
          </div>
          <div className="space-y-2 text-sm text-slate-300">
            {txHash ? (
              <>
                <div className="flex justify-between">
                  <span className="text-slate-400">Network:</span>
                  <span className="capitalize">{network.replace('-', ' ')}</span>
                </div>
                {proof.chain.contract_address && (
                  <div className="flex flex-col gap-1">
                    <span className="text-slate-400">Contract:</span>
                    <span className="break-all font-mono text-xs text-slate-300">{proof.chain.contract_address}</span>
                  </div>
                )}
                <div className="flex flex-col gap-1">
                  <span className="text-slate-400">Transaction Hash:</span>
                  <span className="break-all font-mono text-xs text-slate-300">{txHash}</span>
                </div>
                {proof.chain.block_number && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Block Number:</span>
                    <span>{proof.chain.block_number.toLocaleString()}</span>
                  </div>
                )}
                {proof.chain.anchored_at && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Anchored:</span>
                    <span>{formatDateTime(proof.chain.anchored_at)}</span>
                  </div>
                )}
                <a
                  href={getExplorerUrl(txHash)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-2 rounded-lg bg-brand-500/20 px-3 py-2 text-sm font-medium text-brand-300 transition hover:bg-brand-500/30 hover:text-brand-200"
                >
                  <LinkIcon className="h-4 w-4" />
                  View on Block Explorer
                  <ExternalLink className="h-3 w-3" />
                </a>
              </>
            ) : (
              <p className="text-slate-400">
                {proof.chain.anchor_status === 'pending' || proof.chain.anchor_status === 'submitted'
                  ? 'Blockchain transaction pending...'
                  : 'Blockchain anchor not yet available'}
              </p>
            )}
            {proof.chain.error_message && (
              <div className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-xs text-red-300">{proof.chain.error_message}</p>
              </div>
            )}
          </div>
        </div>

        {/* Error Message */}
        {proof.error_message && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
            <div className="flex items-start gap-2">
              <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
              <div>
                <h3 className="text-sm font-semibold text-red-300">Error</h3>
                <p className="mt-1 text-sm text-red-200">{proof.error_message}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProofPanel;
