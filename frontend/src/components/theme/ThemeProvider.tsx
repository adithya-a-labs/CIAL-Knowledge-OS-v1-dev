import type { ComponentProps } from 'react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';

type ThemeProviderProps = Omit<
  ComponentProps<typeof NextThemesProvider>,
  'attribute' | 'defaultTheme' | 'enableSystem' | 'storageKey'
>;

export default function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      enableColorScheme
      storageKey="cial-theme"
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
