import { ArrowDown, ArrowUp, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Switch } from '@/components/ui/switch';
import { WORKSPACE_WIDGET_REGISTRY } from '@/config/workspaceConfig';
import type { WorkspacePreferences, WorkspaceWidgetId } from '@/data/workspace/workspaceTypes';

interface Props {
  open: boolean;
  value: WorkspacePreferences;
  saving: boolean;
  fallback: boolean;
  onOpenChange: (open: boolean) => void;
  onChange: (value: WorkspacePreferences) => void;
  onSave: () => void;
  onReset: () => void;
}

export default function WorkspaceCustomizeDrawer({ open, value, saving, fallback, onOpenChange, onChange, onSave, onReset }: Props) {
  const patch = (next: Partial<WorkspacePreferences>) => onChange({ ...value, ...next });
  const move = (id: WorkspaceWidgetId, direction: -1 | 1) => {
    const order = [...value.widgetOrder];
    const from = order.indexOf(id);
    const to = from + direction;
    if (from < 0 || to < 0 || to >= order.length) return;
    [order[from], order[to]] = [order[to], order[from]];
    patch({ widgetOrder: order });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Customize workspace</SheetTitle>
          <SheetDescription>Choose defaults and arrange widgets. Security and ownership rules cannot be changed here.</SheetDescription>
        </SheetHeader>
        {fallback ? <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">API unavailable — saving to this browser only.</p> : null}
        <div className="flex-1 space-y-6 py-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-2 text-xs font-semibold text-slate-700">Default tab
              <select value={value.defaultTab} onChange={(event) => patch({ defaultTab: event.target.value as WorkspacePreferences['defaultTab'] })} className="h-9 w-full rounded-md border bg-white px-2 text-sm font-normal">
                {['overview', 'files', 'notes', 'saved', 'activity'].map((tab) => <option key={tab} value={tab}>{tab[0].toUpperCase() + tab.slice(1)}</option>)}
              </select>
            </label>
            <label className="space-y-2 text-xs font-semibold text-slate-700">Default view
              <select value={value.defaultView} onChange={(event) => patch({ defaultView: event.target.value as WorkspacePreferences['defaultView'] })} className="h-9 w-full rounded-md border bg-white px-2 text-sm font-normal">
                <option value="list">List</option><option value="grid">Grid</option>
              </select>
            </label>
            <label className="col-span-2 space-y-2 text-xs font-semibold text-slate-700">Density
              <select value={value.density} onChange={(event) => patch({ density: event.target.value as WorkspacePreferences['density'] })} className="h-9 w-full rounded-md border bg-white px-2 text-sm font-normal">
                <option value="compact">Compact</option><option value="comfortable">Comfortable</option><option value="spacious">Spacious</option>
              </select>
            </label>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <Label htmlFor="right-rail">Show right rail</Label>
            <Switch id="right-rail" checked={value.rightRailVisible} onCheckedChange={(checked) => patch({ rightRailVisible: checked })} />
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Widgets and order</p>
            <div className="space-y-2">
              {value.widgetOrder.map((id, index) => (
                <div key={id} className="flex items-center gap-2 rounded-lg border px-3 py-2">
                  <Checkbox checked={value.visibleWidgets.includes(id)} onCheckedChange={(checked) => patch({ visibleWidgets: checked ? [...value.visibleWidgets, id] : value.visibleWidgets.filter((item) => item !== id) })} aria-label={`Show ${WORKSPACE_WIDGET_REGISTRY[id].label}`} />
                  <span className="min-w-0 flex-1 text-sm">{WORKSPACE_WIDGET_REGISTRY[id].label}</span>
                  <Button variant="ghost" size="icon" disabled={index === 0} onClick={() => move(id, -1)} aria-label={`Move ${id} up`}><ArrowUp size={14} /></Button>
                  <Button variant="ghost" size="icon" disabled={index === value.widgetOrder.length - 1} onClick={() => move(id, 1)} aria-label={`Move ${id} down`}><ArrowDown size={14} /></Button>
                </div>
              ))}
            </div>
          </div>
          <label className="space-y-2 text-xs font-semibold text-slate-700">Recent-item limit
            <input type="number" min={3} max={20} value={value.recentItemLimit} onChange={(event) => patch({ recentItemLimit: Math.max(3, Math.min(20, Number(event.target.value))) })} className="h-9 w-full rounded-md border px-3 text-sm font-normal" />
          </label>
        </div>
        <SheetFooter className="gap-2 sm:justify-between">
          <Button variant="outline" onClick={onReset}><RotateCcw size={15} /> Organization defaults</Button>
          <Button onClick={onSave} disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
