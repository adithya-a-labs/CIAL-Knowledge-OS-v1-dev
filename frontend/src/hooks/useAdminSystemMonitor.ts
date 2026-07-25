import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getAdminSystemMonitor,
  streamAdminSystemMonitor,
} from '@/api/client';
import { ApiError } from '@/api/types';
import type { AdminSystemMonitor } from '@/api/types';

export type MonitorConnectionState =
  | 'connecting'
  | 'live'
  | 'reconnecting'
  | 'disconnected'
  | 'auth-failed';

export function useAdminSystemMonitor() {
  const [data, setData] = useState<AdminSystemMonitor | null>(null);
  const [connection, setConnection] =
    useState<MonitorConnectionState>('connecting');
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastUpdateRef = useRef(0);
  const [restartKey, setRestartKey] = useState(0);

  const reconnect = useCallback(() => {
    setRestartKey((value) => value + 1);
    setConnection('reconnecting');
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let retryTimer: number | undefined;
    let retryCount = 0;

    const accept = (snapshot: AdminSystemMonitor) => {
      lastUpdateRef.current = Date.now();
      setData(snapshot);
      setStale(false);
      setError(null);
      setConnection('live');
      retryCount = 0;
    };

    const connect = async () => {
      if (controller.signal.aborted) return;
      setConnection((current) => (current === 'connecting' ? current : 'reconnecting'));
      try {
        if (!data) accept(await getAdminSystemMonitor(controller.signal));
        await streamAdminSystemMonitor(
          accept,
          controller.signal,
          () => setConnection('live'),
        );
        if (!controller.signal.aborted) throw new Error('Monitor stream closed.');
      } catch (cause) {
        if (controller.signal.aborted) return;
        if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) {
          setConnection('auth-failed');
          setError(cause.message);
          return;
        }
        retryCount += 1;
        setConnection(retryCount > 5 ? 'disconnected' : 'reconnecting');
        setError(cause instanceof Error ? cause.message : 'Live telemetry disconnected.');
        retryTimer = window.setTimeout(connect, Math.min(1000 * 2 ** retryCount, 15_000));
      }
    };

    void connect();
    const staleTimer = window.setInterval(() => {
      if (lastUpdateRef.current && Date.now() - lastUpdateRef.current > 7_000) {
        setStale(true);
      }
    }, 1_000);
    return () => {
      controller.abort();
      window.clearTimeout(retryTimer);
      window.clearInterval(staleTimer);
    };
  }, [restartKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, connection, stale, error, reconnect };
}
