import { useEffect, useState } from "react";
import { getJson } from "./api";

export const POLL_MS = 2000;

export interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

export function useJson<T>(url: string | null, poll: boolean): Loaded<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (url === null) return;
    let live = true;
    const load = () => {
      getJson<T>(url).then(
        (result) => {
          if (live) setData(result);
        },
        (reason: unknown) => {
          if (live) setError(String(reason));
        },
      );
    };
    load();
    const timer = poll ? setInterval(load, POLL_MS) : undefined;
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [url, poll, version]);

  return {
    data,
    error,
    reload: () => {
      setVersion((current) => current + 1);
    },
  };
}
