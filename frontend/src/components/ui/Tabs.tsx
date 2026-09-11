import { useState } from 'react';
import { cn } from '@/lib/utils';

export interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  onChange?: (id: string) => void;
}

export function Tabs({ tabs, defaultTab, onChange }: TabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0].id);

  const select = (id: string) => {
    setActive(id);
    onChange?.(id);
  };

  const handleKeyDown = (event: React.KeyboardEvent, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextId = tabs[nextIndex].id;
    setActive(nextId);
    onChange?.(nextId);
    document.getElementById(`tab-${nextId}`)?.focus();
  };

  return (
    <div>
      <div role="tablist" className="flex gap-1 border-b border-line">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`tabpanel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onKeyDown={(e) => handleKeyDown(e, index)}
            onClick={() => select(tab.id)}
            className={cn(
              'cursor-pointer rounded-t-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
              active === tab.id
                ? 'border-b-2 border-primary text-primary'
                : 'border-b-2 border-transparent text-fg-muted hover:text-fg'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div id={`tabpanel-${active}`} role="tabpanel" aria-labelledby={`tab-${active}`} className="pt-4">
        {tabs.find((tab) => tab.id === active)?.content}
      </div>
    </div>
  );
}
