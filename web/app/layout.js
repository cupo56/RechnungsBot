import './globals.css';
import Navigation from '@/components/Navigation';

export const metadata = {
  title: 'RechnungsBot — Handelsagentur Adis Sefer',
  description: 'Rechnungen & Lieferscheine automatisch erstellen. Modernes Invoice-Management für die Handelsagentur Adis Sefer.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="de">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Navigation />
        <main>{children}</main>
      </body>
    </html>
  );
}
