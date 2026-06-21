import { NextResponse } from 'next/server';

export async function POST(request) {
  try {
    const body = await request.json();
    const { api_url, api_key, action, ...data } = body;

    if (!api_url || !api_key) {
      return NextResponse.json(
        { success: false, message: 'API URL oder API Key fehlt in der Anfrage.' },
        { status: 400 }
      );
    }

    const targetUrl = `${api_url.replace(/\/$/, '')}/api.php`;
    const payload = { action, api_key, ...data };

    // Setze strictSSL false equivalent für fetch in Node (nicht strikt für self-signed certs)
    const fetchOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      // In production you might need an httpsAgent with rejectUnauthorized: false 
      // if dealing with invalid certs, but fetch handles normal HTTPS fine.
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
