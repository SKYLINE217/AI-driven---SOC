/**
 * Vercel BFF — Auth proxy
 * Route: /api/auth/[...path]
 *
 * Forwards auth requests to the backend FastAPI server.
 * Injects the backend base URL from a Vercel environment variable
 * so it is never exposed to the client bundle.
 */
import type { VercelRequest, VercelResponse } from '@vercel/node';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const path = (req.query.path as string[])?.join('/') || '';
  const targetUrl = `${BACKEND_URL}/api/auth/${path}`;

  try {
    const response = await fetch(targetUrl, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        ...(req.headers.authorization ? { Authorization: req.headers.authorization } : {}),
      },
      body: req.method !== 'GET' && req.method !== 'HEAD'
        ? JSON.stringify(req.body)
        : undefined,
    });

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    res.status(502).json({ error: 'Backend unavailable', detail: String(err) });
  }
}
