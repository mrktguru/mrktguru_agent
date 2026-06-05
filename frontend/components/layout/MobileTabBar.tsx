"use client";

export type TabBarItem = {
  key: string;
  label: string;
  icon: React.ReactNode;
};

/**
 * Фиксированный нижний таб-бар для мобильных экранов (< md).
 * Используется на site/[id] для переключения Задачи/Аудит/История/Инфо.
 * Учитывает safe-area нижней зоны (iPhone home indicator).
 */
export default function MobileTabBar({
  items,
  active,
  onSelect,
}: {
  items: TabBarItem[];
  active: string;
  onSelect: (key: string) => void;
}) {
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-surface border-t border-border flex pb-safe">
      {items.map((it) => {
        const on = it.key === active;
        return (
          <button
            key={it.key}
            onClick={() => onSelect(it.key)}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-2 min-h-[52px] transition-colors ${
              on ? "text-accent" : "text-text-muted hover:text-text-main"
            }`}
          >
            <span className="text-lg leading-none">{it.icon}</span>
            <span className="text-[10px] font-medium leading-none">{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
