"use client";

import React, { createContext, useContext, useState, type ReactNode } from "react";
import { translations, type Lang, type Translations } from "@/lib/i18n";

interface LanguageContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("enterprise_lang") as Lang | null;
        if (saved === "en" || saved === "tr") return saved;
      } catch {
        // ignore
      }
    }
    return "en";
  });

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("enterprise_lang", l);
    } catch {
      // ignore
    }
  };

  const t = translations[lang] as Translations;

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    return {
      lang: "en" as Lang,
      setLang: () => {},
      t: translations.en as Translations,
    };
  }
  return ctx;
}
