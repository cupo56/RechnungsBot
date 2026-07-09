'use client';

export default function Toast({ toast, onDismiss }) {
  if (!toast) return null;
  return (
    <div className={`toast ${toast.type === 'error' ? 'toast-error' : 'toast-success'}`}
      onClick={onDismiss}>
      {toast.text}
    </div>
  );
}
