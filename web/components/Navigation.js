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
          
          <label 
            className="nav-link" 
            style={{ cursor: 'pointer' }}
            title="Einstellungen & Vorlagen importieren (.json)"
          >
            ⚙️ Import
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
