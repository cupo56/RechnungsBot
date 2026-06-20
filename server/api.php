<?php
/**
 * RechnungsBot API – PHP-Middleware für die MySQL-Datenbank auf World4You.
 *
 * Diese Datei empfängt JSON-POST-Requests vom Desktop-Programm und führt
 * die entsprechenden Datenbankoperationen aus.
 *
 * INSTALLATION:
 * 1. Diese Datei + config.php auf den World4You-Webspace hochladen
 * 2. In config.php die DB-Zugangsdaten und den API-Key eintragen
 * 3. Im Programm die API-URL eingeben (z.B. https://deinedomain.at/rechnungsbot)
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Preflight OPTIONS-Request beantworten
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Nur POST erlauben
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'Nur POST-Requests erlaubt.']);
    exit;
}

// Config laden
require_once __DIR__ . '/config.php';

// JSON-Body parsen
$raw = file_get_contents('php://input');
$input = json_decode($raw, true);

if (!$input || !isset($input['action'])) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Ungültiger Request: action fehlt.']);
    exit;
}

// API-Key prüfen
if (!isset($input['api_key']) || $input['api_key'] !== API_KEY) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Ungültiger API-Key.']);
    exit;
}

// Datenbankverbindung herstellen
try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';port=' . DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::MYSQL_ATTR_INIT_COMMAND => "SET NAMES utf8mb4",
        ]
    );
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'DB-Verbindung fehlgeschlagen: ' . $e->getMessage()]);
    exit;
}

// ── Aktionen ──────────────────────────────────────────────────

$action = $input['action'];

switch ($action) {

    // ── Verbindungstest ───────────────────────────────────────
    case 'test':
        echo json_encode(['success' => true, 'message' => 'Verbindung erfolgreich!']);
        break;

    // ── Datenbank initialisieren ──────────────────────────────
    case 'init':
        try {
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS invoices (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    invoice_number  VARCHAR(50)  NOT NULL,
                    invoice_date    VARCHAR(20)  NOT NULL,
                    document_type   VARCHAR(30)  NOT NULL DEFAULT 'rechnung',
                    customer_name   VARCHAR(255) NOT NULL,
                    customer_street VARCHAR(255) DEFAULT '',
                    customer_plz    VARCHAR(100) DEFAULT '',
                    customer_country VARCHAR(100) DEFAULT '',
                    customer_vat    VARCHAR(50)  DEFAULT '',
                    total_netto     DECIMAL(12,2) DEFAULT 0.00,
                    total_brutto    DECIMAL(12,2) DEFAULT 0.00,
                    ust_percent     DECIMAL(5,2)  DEFAULT 0.00,
                    item_count      INT DEFAULT 0,
                    is_export       TINYINT(1) DEFAULT 0,
                    pdf_filename    VARCHAR(255) NOT NULL,
                    pdf_data        LONGBLOB     NOT NULL,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_invoice_number (invoice_number),
                    INDEX idx_customer_name  (customer_name),
                    INDEX idx_invoice_date   (invoice_date),
                    INDEX idx_created_at     (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ");
            echo json_encode(['success' => true, 'message' => 'Datenbank initialisiert.']);
        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'Init fehlgeschlagen: ' . $e->getMessage()]);
        }
        break;

    // ── Rechnung speichern ────────────────────────────────────
    case 'save':
        try {
            $required = ['invoice_number', 'invoice_date', 'customer_name', 'pdf_filename', 'pdf_data'];
            foreach ($required as $field) {
                if (empty($input[$field])) {
                    echo json_encode(['success' => false, 'message' => "Pflichtfeld fehlt: $field"]);
                    exit;
                }
            }

            // PDF-Daten von Base64 dekodieren
            $pdf_binary = base64_decode($input['pdf_data'], true);
            if ($pdf_binary === false) {
                echo json_encode(['success' => false, 'message' => 'Ungültige PDF-Daten (Base64-Fehler).']);
                exit;
            }

            $stmt = $pdo->prepare("
                INSERT INTO invoices
                    (invoice_number, invoice_date, document_type,
                     customer_name, customer_street, customer_plz,
                     customer_country, customer_vat,
                     total_netto, total_brutto, ust_percent,
                     item_count, is_export, pdf_filename, pdf_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ");

            $stmt->execute([
                $input['invoice_number'],
                $input['invoice_date'],
                $input['document_type'] ?? 'rechnung',
                $input['customer_name'],
                $input['customer_street'] ?? '',
                $input['customer_plz'] ?? '',
                $input['customer_country'] ?? '',
                $input['customer_vat'] ?? '',
                floatval($input['total_netto'] ?? 0),
                floatval($input['total_brutto'] ?? 0),
                floatval($input['ust_percent'] ?? 0),
                intval($input['item_count'] ?? 0),
                intval($input['is_export'] ?? 0),
                $input['pdf_filename'],
                $pdf_binary,
            ]);

            $id = $pdo->lastInsertId();
            echo json_encode(['success' => true, 'message' => 'Erfolgreich gespeichert.', 'id' => $id]);

        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'Speichern fehlgeschlagen: ' . $e->getMessage()]);
        }
        break;

    // ── Rechnungsliste abrufen ────────────────────────────────
    case 'list':
        try {
            $sql = "SELECT id, invoice_number, invoice_date, document_type,
                           customer_name, total_netto, total_brutto, ust_percent,
                           item_count, is_export, pdf_filename, created_at
                    FROM invoices WHERE 1=1";
            $params = [];

            if (!empty($input['search'])) {
                $sql .= " AND (invoice_number LIKE ? OR customer_name LIKE ?)";
                $like = '%' . $input['search'] . '%';
                $params[] = $like;
                $params[] = $like;
            }

            if (!empty($input['doc_type']) && $input['doc_type'] !== 'alle') {
                $sql .= " AND document_type = ?";
                $params[] = $input['doc_type'];
            }

            $sql .= " ORDER BY created_at DESC LIMIT 500";

            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            $rows = $stmt->fetchAll();

            // Dezimalwerte als float für JSON
            foreach ($rows as &$row) {
                $row['total_netto'] = floatval($row['total_netto']);
                $row['total_brutto'] = floatval($row['total_brutto']);
                $row['ust_percent'] = floatval($row['ust_percent']);
                $row['item_count'] = intval($row['item_count']);
                $row['is_export'] = intval($row['is_export']);
                $row['id'] = intval($row['id']);
            }

            echo json_encode(['success' => true, 'invoices' => $rows]);

        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'Abruf fehlgeschlagen: ' . $e->getMessage()]);
        }
        break;

    // ── PDF einer Rechnung abrufen ────────────────────────────
    case 'get_pdf':
        try {
            if (empty($input['invoice_id'])) {
                echo json_encode(['success' => false, 'message' => 'invoice_id fehlt.']);
                exit;
            }

            $stmt = $pdo->prepare("SELECT pdf_data, pdf_filename FROM invoices WHERE id = ?");
            $stmt->execute([intval($input['invoice_id'])]);
            $row = $stmt->fetch();

            if (!$row) {
                echo json_encode(['success' => false, 'message' => 'Rechnung nicht gefunden.']);
                exit;
            }

            // PDF als Base64 zurückgeben
            echo json_encode([
                'success' => true,
                'pdf_data' => base64_encode($row['pdf_data']),
                'pdf_filename' => $row['pdf_filename'],
            ]);

        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'PDF-Abruf fehlgeschlagen: ' . $e->getMessage()]);
        }
        break;

    // ── Rechnung löschen ──────────────────────────────────────
    case 'delete':
        try {
            if (empty($input['invoice_id'])) {
                echo json_encode(['success' => false, 'message' => 'invoice_id fehlt.']);
                exit;
            }

            $stmt = $pdo->prepare("DELETE FROM invoices WHERE id = ?");
            $stmt->execute([intval($input['invoice_id'])]);

            if ($stmt->rowCount() > 0) {
                echo json_encode(['success' => true, 'message' => 'Eintrag gelöscht.']);
            } else {
                echo json_encode(['success' => false, 'message' => 'Eintrag nicht gefunden.']);
            }

        } catch (PDOException $e) {
            echo json_encode(['success' => false, 'message' => 'Löschen fehlgeschlagen: ' . $e->getMessage()]);
        }
        break;

    // ── Anzahl abrufen ────────────────────────────────────────
    case 'count':
        try {
            $stmt = $pdo->query("SELECT COUNT(*) as cnt FROM invoices");
            $row = $stmt->fetch();
            echo json_encode(['success' => true, 'count' => intval($row['cnt'])]);
        } catch (PDOException $e) {
            echo json_encode(['success' => true, 'count' => 0]);
        }
        break;

    default:
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => "Unbekannte Aktion: $action"]);
}
