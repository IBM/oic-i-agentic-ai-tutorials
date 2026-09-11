import { Theme as CarbonThemeProvider } from "@carbon/react";
import { createContext, useContext, useEffect, useState } from "react";

const LIGHT_THEME: CarbonTheme = "white";
const DARK_THEME: CarbonTheme = "g100";

type CarbonTheme = "g10" | "g90" | "g100" | "white";
export type Theme = "light" | "dark" | "system";

type ThemeProviderProps = {
  children: React.ReactNode;
  defaultTheme?: Theme;
  storageKey?: string;
};

type ThemeProviderState = {
  theme: Theme;
  actualTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
};

const initialState: ThemeProviderState = {
  theme: "system",
  actualTheme: "light",
  setTheme: () => null,
};

const ThemeProviderContext = createContext<ThemeProviderState>(initialState);

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "carbon-theme",
  ...props
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(storageKey) as Theme) || defaultTheme,
  );
  const [actualTheme, setActualTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light";

      setActualTheme(systemTheme);
      return;
    }

    setActualTheme(theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.classList.remove(
      "cds--white",
      "cds--g10",
      "cds--g90",
      "cds--g100",
      "dark",
    );

    const carbonTheme = actualTheme === "dark" ? DARK_THEME : LIGHT_THEME;
    document.documentElement.classList.add(`cds--${carbonTheme}`);
    if (actualTheme === "dark") {
      document.documentElement.classList.add("dark");
    }
  }, [actualTheme]);

  const value = {
    theme,
    actualTheme,
    setTheme: (theme: Theme) => {
      localStorage.setItem(storageKey, theme);
      setTheme(theme);
    },
  };

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      <CarbonThemeProvider
        theme={actualTheme === "dark" ? DARK_THEME : LIGHT_THEME}
      >
        {children}
      </CarbonThemeProvider>
    </ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);

  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider");

  return context;
};
