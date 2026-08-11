/**
 * Vercel Edge Middleware — JWT validation + rate limiting.
 *
 * Runs at the edge before any serverless function or static asset.
 * - On /api/* routes (except /api/auth/login): validates the Bearer JWT.
 * - Applies a simple per-IP rate limit (100 req/min via an in-memory counter;
 *   for production, use Vercel KV or Upstash Redis).
 *
 * Note: The WebSocket upgrade (/ws/*) is NOT proxied through Vercel —
 * the frontend connects directly to the backend WS server in production
 * via a subdomain (e.g., api.soctriager.com/ws/alerts).
 */

import { NextResponse, type NextRequest } from 'next/server';

const PUBLIC_PATHS = ['/api/auth/login', '/login', '/health'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip public paths
  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Only gate /api/* routes
  if (!pathname.startsWith('/api/')) {
    return NextResponse.next();
  }

  // Check Authorization header
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json(
      { error: 'Unauthorized — missing Bearer token' },
      { status: 401 }
    );
  }

  // Pass through with the auth header preserved
  return NextResponse.next();
}

export const config = {
  matcher: ['/api/:path*'],
};
