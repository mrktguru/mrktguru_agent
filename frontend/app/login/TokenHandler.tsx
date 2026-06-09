"use client";

import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

export default function TokenHandler({ onToken }: { onToken: (token: string) => void }) {
  const params = useSearchParams();
  useEffect(() => {
    const token = params.get("token");
    if (token) onToken(token);
  }, [params, onToken]);
  return null;
}
