'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

  const links = [
    { href: '/', label: '📄 Rechnung', desc: 'Rechnungen & Lieferscheine' },
    { href: '/compare', label: '🔍 Vergleich', desc: 'Excel-Listen abgleichen' },
    { href: '/provision', label: '💰 Provision', desc: 'Abrechnung erstellen' },
    { href: '/credit-note', label: '↩️ Gutschrift', desc: 'Stornos & Gutschriften' },
    { href: '/database', label: '🗄️ Datenbank', desc: 'Archiv & Suche' },
  ];

  return (
    <nav className="top-nav">
      <div className="nav-container">
        <div className="nav-logo">
          <strong>Adis Sefer</strong>
          <span>RechnungsBot</span>
        </div>
        <div className="nav-links">
          {links.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`nav-link ${isActive ? 'active' : ''}`}
                title={link.desc}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
