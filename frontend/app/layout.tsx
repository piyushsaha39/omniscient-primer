import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

export const metadata = {
  title: "OmniPrimer — Command Center",
  description: "Pre-cognitive productivity companion",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <head>
          <link
            rel="stylesheet"
            href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0"
          />
        </head>
        <body className="bg-slate-950 text-slate-100 antialiased">{children}</body>
      </html>
    </ClerkProvider>
  );
}