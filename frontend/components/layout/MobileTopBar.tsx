"use client";

/**
 * Фиксированная верхняя панель для мобильных экранов (< md).
 * Слева — кнопка-бургер, по центру — заголовок, справа — опциональный слот.
 * На десктопе скрыта (md:hidden); десктопный хедер живёт отдельно.
 */
export default function MobileTopBar({
  title,
  onMenu,
  right,
}: {
  title: string;
  onMenu: () => void;
  right?: React.ReactNode;
}) {
  return (
    <header className="md:hidden fixed top-0 inset-x-0 z-40 h-[57px] bg-surface border-b border-border flex items-center gap-2 px-3">
      <button
        onClick={onMenu}
        aria-label="Меню"
        className="w-10 h-10 -ml-1 flex items-center justify-center rounded-xl text-text-main hover:bg-surface-2 transition-colors flex-shrink-0"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M2.5 5h13M2.5 9h13M2.5 13h13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      <h1 className="flex-1 text-sm font-semibold text-text-main truncate">{title}</h1>
      {right && <div className="flex items-center flex-shrink-0">{right}</div>}
    </header>
  );
}
