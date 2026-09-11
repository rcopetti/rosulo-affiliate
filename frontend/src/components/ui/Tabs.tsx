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

  return (
    <div>
      <div role="tablist" className="flex gap-1 border-b border-line">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
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
      <div role="tabpanel" className="pt-4">
        {tabs.find((tab) => tab.id === active)?.content}
      </div>
    </div>
  );
}
