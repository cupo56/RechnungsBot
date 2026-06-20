<?php
/**
 * RechnungsBot API – Sicherheitsschutz.
 * Verhindert das Auflisten des Verzeichnisses.
 */
header('HTTP/1.1 403 Forbidden');
echo 'Zugriff verweigert.';
