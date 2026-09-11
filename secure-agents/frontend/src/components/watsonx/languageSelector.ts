// Locale options: en, fr, de, it, ja, es, ko, pt-BR, zh-TW, zh-CN
export const defaultLocale = "en";
export const languageMap: Record<string, string> = {
  de: "Deutsch",
  en: "English",
  es: "Español",
  fr: "Français",
  it: "Italiano",
  ja: "日本語",
};

// Each language-option must have an id and a text property
export const languageOptions = [
  {
    id: "de",
    text: "Deutsch",
    onClick: () => handleLanguageChange("de"),
  },
  {
    id: "en",
    text: "English",
    onClick: () => handleLanguageChange("en"),
  },
  {
    id: "es",
    text: "Español",
    onClick: () => handleLanguageChange("es"),
  },
  {
    id: "fr",
    text: "Français",
    onClick: () => handleLanguageChange("fr"),
  },
  {
    id: "ja",
    text: "日本語",
    onClick: () => handleLanguageChange("ja"),
  },
];

// Handler for language change
export const handleLanguageChange = (locale: string) => {
  if (window.wxoLoader?.chatInstance) {
    const chatInstance = window.wxoLoader.chatInstance;
    chatInstance.updateLocale(locale);
    chatInstance.updateCustomHeaderItems([
      {
        id: "language-selector",
        type: "dropdown",
        text: languageMap[locale] || languageMap.en,
        icon: "",
        align: "right",
        items: languageOptions,
      },
    ]);
  }
};

export const getCustomLanguageSelector = () => {
  const currentLocale = window.wxoLoader?.chatInstance?.getLocale() || "en";
  return {
    id: "language-selector",
    type: "dropdown",
    text: languageMap[currentLocale] || languageMap.en,
    icon: "",
    align: "right",
    items: languageOptions,
  };
};
