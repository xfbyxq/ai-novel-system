import { useEffect, useRef, useCallback } from 'react';

export function usePolling(
  callback: () => Promise<void>,
  interval: number,
  enabled: boolean,
) {
  const savedCallback = useRef(callback);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = undefined;
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      stop();
      return;
    }

    // Run immediately, then at interval
    savedCallback.current();
    timerRef.current = setInterval(() => {
      savedCallback.current();
    }, interval);

    return stop;
  }, [enabled, interval, stop]);

  return { stop };
}
