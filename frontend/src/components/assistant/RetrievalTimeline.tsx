import { CheckCircle2, Loader2 } from 'lucide-react';
import { RETRIEVAL_STAGES } from '@/data/assistantData';

interface RetrievalTimelineProps {
  activeStageIndex: number;
}

export default function RetrievalTimeline({ activeStageIndex }: RetrievalTimelineProps) {
  return (
    <div className="ce-card max-w-[94%] px-4 py-3 sm:max-w-[84%] lg:max-w-[80%]" data-testid="retrieval-timeline">
      <p className="mb-3 text-xs font-semibold text-foreground">Preparing grounded answer</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {RETRIEVAL_STAGES.map((stage, index) => {
          const completed = index < activeStageIndex;
          const active = index === activeStageIndex;
          return (
            <div key={stage} className="flex items-center gap-2 text-xs">
              {completed ? (
                <CheckCircle2 size={14} className="text-primary" />
              ) : active ? (
                <Loader2 size={14} className="animate-spin text-[#b76a09]" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full border border-border" />
              )}
              <span className={active ? 'font-semibold text-foreground' : 'text-muted-foreground'}>
                {stage}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
