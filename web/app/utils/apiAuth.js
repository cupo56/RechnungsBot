// Shared secret sent with every request to the Flask API (/api/parse,
// /api/generate, /api/provision, /api/credit-note). It is bundled into the
// client JS (NEXT_PUBLIC_*), so it is not a real access-control secret — it
// only deters casual/automated abuse of the bare API URL by outsiders who
// never loaded the app. Real secrets (DB_API_KEY, DB_API_URL) stay server-only.
export function apiHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra };
  const secret = process.env.NEXT_PUBLIC_API_SHARED_SECRET;
  if (secret) {
    headers['Authorization'] = `Bearer ${secret}`;
  }
  return headers;
}
