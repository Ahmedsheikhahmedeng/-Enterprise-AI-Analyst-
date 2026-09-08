"use client";

import React, { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "./client";

import { LanguageProvider } from "@/contexts/language-context";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => createQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>{children}</LanguageProvider>
    </QueryClientProvider>
  );
}
