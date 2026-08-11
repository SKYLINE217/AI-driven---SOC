/**
 * Vercel BFF — Alerts proxy
 * Route: /api/alerts/[...path]
 *
 * Validates the Authorization Bearer JWT before forwarding to the backend.
 * The backend base URL is injected from a Vercel environment variable.
 */
import type { VercelRequest, VercelResponse } from '@vercel/node';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or invalid Authorization header' });
  }

  const path = (req.query.path as string[])?.join('/') || '';
  const queryString = new URLSearchParams(
    Object.entries(req.query as Record<string, string>).filter(([k]) => k !== 'path')
  ).toString();
  const targetUrl = `${BACKEND_URL}/api/alerts${path ? `/${path}` : ''}${queryString ? `?${queryString}` : ''}`;

  try {
    const response = await fetch(targetUrl, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: authHeader,
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
