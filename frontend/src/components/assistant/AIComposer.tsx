import type { ReactNode, RefObject } from 'react';
import { Send } from 'lucide-react';
import { cn } from '@/lib/utils';

export function AIComposerFrame({ children, className, testId = 'compact-chat-composer' }: { children: ReactNode; className?: string; testId?: string }) {
  return <div className={cn('assistant-composer mx-auto grid min-h-[108px] w-full max-w-6xl grid-cols-[minmax(0,1fr)_auto] grid-rows-[minmax(3rem,auto)_auto] rounded-[1.4rem] border border-border bg-card/95 shadow-sm transition-[transform,border-color,box-shadow,background-color] duration-[var(--motion-duration-short)] ease-[var(--motion-ease-enter)]',className)} data-testid={testId}>{children}</div>;
}

export default function AIComposer({ value, onChange, onSubmit, placeholder, disabled=false, toolbar, leadingAction, textareaRef, testId='shared-ai-composer' }: { value:string; onChange:(value:string)=>void; onSubmit:()=>void|Promise<void>; placeholder:string; disabled?:boolean; toolbar?:ReactNode; leadingAction?:ReactNode; textareaRef?:RefObject<HTMLTextAreaElement|null>; testId?:string }) {
  return <AIComposerFrame testId={testId}>
    <div className="col-start-1 row-start-1 min-w-0 px-5 pb-1 pt-4 sm:px-7"><textarea ref={textareaRef} value={value} onChange={(event)=>onChange(event.target.value)} onKeyDown={(event)=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();void onSubmit();}}} rows={1} placeholder={placeholder} aria-label={placeholder} className="block max-h-40 min-h-9 w-full resize-none overflow-y-auto bg-transparent py-1 text-[15px] leading-6 text-foreground outline-none placeholder:text-muted-foreground sm:text-base" data-testid="input-chat"/></div>
    <div className="col-start-1 row-start-2 flex min-w-0 items-center gap-1 px-3 pb-3 sm:px-5">{leadingAction}<div className="scrollbar-soft min-w-0 flex-1 overflow-x-auto pb-0.5">{toolbar}</div></div>
    <button type="button" onClick={()=>void onSubmit()} disabled={disabled||!value.trim()} className="composer-send col-start-2 row-span-2 row-start-1 mb-3 mr-3 inline-flex h-11 w-11 self-end items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition hover:bg-primary/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:bg-muted disabled:text-muted-foreground disabled:shadow-none sm:h-12 sm:w-12" aria-label="Send message" data-testid="button-send"><Send size={18}/></button>
  </AIComposerFrame>;
}
