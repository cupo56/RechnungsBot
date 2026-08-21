'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FileText, GitCompare, Link as LinkIcon, Wallet, Undo2, User, Database, Settings } from 'lucide-react';

export default function Navigation() {
  const pathname = usePathname();

  const links = [
    { href: '/', label: 'Rechnung', icon: FileText, desc: 'Rechnungen & Lieferscheine' },
    { href: '/compare', label: 'Vergleich', icon: GitCompare, desc: 'Excel-Listen abgleichen' },
    { href: '/order', label: 'Order', icon: LinkIcon, desc: 'Bestellmengen per EAN übernehmen' },
    { href: '/provision', label: 'Provision', icon: Wallet, desc: 'Abrechnung erstellen' },
    { href: '/credit-note', label: 'Gutschrift', icon: Undo2, desc: 'Stornos & Gutschriften' },
    { href: '/endkunde', label: 'Endkunde', icon: User, desc: 'Rechnung für Endkunden manuell erstellen' },
    { href: '/database', label: 'Datenbank', icon: Database, desc: 'Archiv & Suche' },
  ];

  const handleImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        
        // Merge with existing config
        const existingStr = localStorage.getItem('rechnungsbot_config');
        let existing = {};
        try { if (existingStr) existing = JSON.parse(existingStr); } catch(err){}

        const merged = { ...existing, ...json };
        localStorage.setItem('rechnungsbot_config', JSON.stringify(merged));
        
        alert('Vorlagen und Einstellungen erfolgreich importiert!');
        window.location.reload();
      } catch (err) {
        alert('Fehler beim Importieren der Datei: ' + err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = ''; // reset input
  };

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
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`nav-link ${isActive ? 'active' : ''}`}
                title={link.desc}
              >
                <Icon size={16} strokeWidth={2} className="nav-link-icon" />
                {link.label}
              </Link>
            );
          })}

          <label
            className="nav-link"
            style={{ cursor: 'pointer' }}
            title="Einstellungen & Vorlagen importieren (.json)"
          >
            <Settings size={16} strokeWidth={2} className="nav-link-icon" />
            Import
            <input
              type="file" 
              accept=".json" 
              style={{ display: 'none' }} 
              onChange={handleImport} 
            />
          </label>
        </div>
      </div>
    </nav>
  );
}
