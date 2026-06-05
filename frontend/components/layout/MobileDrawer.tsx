"use client";

import { useEffect } from "react";

/**
 * Выезжающая панель для мобильных экранов (< md).
 * Используется как бургер-меню (side="left") и как инфо-sheet (side="right").
 * На десктопе скрыта целиком (md:hidden).
 */
export default function MobileDrawer({
  open,
  onClose,
  side = "left",
  children,
}: {
  open: boolean;
  onClose: () => void;
  side?: "left" | "right";
  children: React.ReactNode;
}) {
  // Закрытие по Esc + блокировка скролла body, пока панель открыта.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  const isLeft = side === "left";
  const hiddenTransform = isLeft ? "-translate-x-full" : "translate-x-full";

  return (
    <div className={`md:hidden fixed inset-0 z-50 ${open ? "" : "pointer-events-none"}`} aria-hidden={!open}>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-black/30 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
      />
      {/* Panel */}
      <aside
        className={`absolute top-0 ${isLeft ? "left-0" : "right-0"} h-full w-[82%] max-w-xs bg-surface ${
          isLeft ? "border-r" : "border-l"
        } border-border shadow-modal flex flex-col overflow-y-auto transition-transform duration-200 ${
          open ? "translate-x-0" : hiddenTransform
        }`}
      >
        {children}
      </aside>
    </div>
  );
}
