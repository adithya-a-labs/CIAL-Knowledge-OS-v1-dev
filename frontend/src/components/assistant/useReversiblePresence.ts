import { useEffect, useRef, useState } from 'react';
import { useReducedMotionPreference } from '@/hooks/useReducedMotionPreference';

const PANEL_TRANSITION_MS = 220;
const REDUCED_MOTION_TRANSITION_MS = 140;

/**
 * Keeps a surface mounted long enough for its exit transition and lets a rapid
 * reopen retarget the same CSS transition from its current visual state.
 */
export function useReversiblePresence(open: boolean, durationMs = PANEL_TRANSITION_MS) {
  const reducedMotion = useReducedMotionPreference();
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(open);
  const frameRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);

    if (open) {
      setMounted(true);
      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = null;
        setVisible(true);
      });
    } else {
      setVisible(false);
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        setMounted(false);
      }, reducedMotion ? REDUCED_MOTION_TRANSITION_MS : durationMs);
    }

    return () => {
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, [durationMs, open, reducedMotion]);

  return { mounted, visible, reducedMotion };
}
