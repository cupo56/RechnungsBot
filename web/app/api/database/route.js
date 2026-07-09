import { NextResponse } from 'next/server';

// ─── SSRF Protection ────────────────────────────────────────────────
// The DB API URL is read exclusively from the server-side environment
// variable DB_API_URL. The client may NOT specify an arbitrary URL.
// As defense-in-depth, an allowlist restricts which hosts the proxy
// may contact even if the env var is misconfigured.
const ALLOWED_HOSTS = [
  'sefer-trading.com',
  'www.sefer-trading.com',
];

function isAllowedUrl(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    return (
      ALLOWED_HOSTS.includes(host) &&
      (parsed.protocol === 'https:' || parsed.protocol === 'http:')
    );
  } catch {
    return false;
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    // api_url is intentionally NOT destructured from the body.
    // The client may still send api_key for backward compat, but it is
    // overridden by the env var if present.
    const { api_key: clientApiKey, action, ...data } = body;

    // Server-side configuration takes precedence
    const apiUrl = process.env.DB_API_URL;
    const apiKey = process.env.DB_API_KEY || clientApiKey;

    if (!apiUrl) {
      return NextResponse.json(
        {
          success: false,
          message:
            'DB_API_URL ist nicht als Umgebungsvariable konfiguriert. ' +
            'Bitte in den Vercel Environment Variables oder in .env.local setzen.',
        },
        { status: 500 }
      );
    }

    if (!apiKey) {
      return NextResponse.json(
        { success: false, message: 'API Key fehlt (weder in ENV noch in der Anfrage).' },
        { status: 400 }
      );
    }

    // Defense-in-depth: validate against allowlist
    if (!isAllowedUrl(apiUrl)) {
      return NextResponse.json(
        {
          success: false,
          message:
            `DB_API_URL verweist auf einen nicht erlaubten Host. ` +
            `Erlaubt: ${ALLOWED_HOSTS.join(', ')}`,
        },
        { status: 403 }
      );
    }

    const targetUrl = `${apiUrl.replace(/\/$/, '')}/api.php`;
    const payload = { action, api_key: apiKey, ...data };

    const fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    };

    const response = await fetch(targetUrl, fetchOptions);
    const result = await response.json();

    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { success: false, message: `Proxy-Fehler: ${err.message}` },
      { status: 500 }
    );
  }
}
