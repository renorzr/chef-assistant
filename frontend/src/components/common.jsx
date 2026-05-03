import React, { useState } from "react";
import { toDisplayImageUrl } from "../utils/image";

export function Spinner() {
  return <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-black" />;
}

export function LoadingBlock() {
  return (
    <div className="flex items-center justify-center py-12">
      <Spinner />
    </div>
  );
}

export function IconButton({ onClick, children, title, active = false, disabled = false, tone = "default" }) {
  const toneClass =
    tone === "danger"
      ? "bg-red-50 text-red-600"
      : active
        ? "bg-black text-white"
        : "bg-gray-100 text-gray-700";

  return (
    <button
      onClick={onClick}
      title={title}
      disabled={disabled}
      className={`flex h-9 w-9 items-center justify-center rounded-full text-lg shadow-sm transition ${toneClass} disabled:opacity-40`}
    >
      {children}
    </button>
  );
}

export function BottomSheet({ open, title, onClose, children }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <button className="absolute inset-0 bg-black/30" onClick={onClose} aria-label="关闭弹窗" />
      <div className="relative flex max-h-[85vh] w-full max-w-sm flex-col rounded-t-3xl bg-white p-4 shadow-2xl">
        <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-gray-200" />
        <div className="mb-3 flex items-center justify-between">
          <div className="font-semibold">{title}</div>
          <button onClick={onClose} className="rounded-full bg-gray-100 px-2 py-1 text-sm">
            关闭
          </button>
        </div>
        <div className="min-h-0 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

export function ErrorBlock({ onRetry }) {
  return (
    <div className="py-10 text-center">
      <div className="mb-3 text-sm text-gray-500">加载失败</div>
      <button onClick={onRetry} className="rounded-xl bg-black px-4 py-2 text-sm text-white">
        重试
      </button>
    </div>
  );
}

export function ImageOrPlaceholder({ src, alt, className, placeholderClassName }) {
  const [broken, setBroken] = useState(false);
  const displayUrl = toDisplayImageUrl(src);

  if (!displayUrl || broken) {
    return <div className={placeholderClassName} />;
  }

  return <img src={displayUrl} alt={alt} className={className} onError={() => setBroken(true)} />;
}

export function TabButton({ label, active, onClick }) {
  return (
    <button onClick={onClick} className={`flex-1 py-2 text-sm ${active ? "border-t-2 border-black font-bold" : "text-gray-500"}`}>
      {label}
    </button>
  );
}
