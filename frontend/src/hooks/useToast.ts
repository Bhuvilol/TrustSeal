import { useContext } from 'react';
import ToastContext from '@/context/ToastContext';

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }

  return {
    showToast: context.showToast,
    showSuccess: (message: string) => context.showToast('success', message),
    showError: (message: string) => context.showToast('error', message),
    showInfo: (message: string) => context.showToast('info', message),
  };
}
