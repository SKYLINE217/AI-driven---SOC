/**
 * BFF: GET /api/alerts
 * JWT-gated proxy to backend GET /alerts with all filter params forwarded.
 */

import { verifyJWT, unauthorizedResponse, proxyToBackend } from '../../_lib/auth'

export async function GET(request: Request): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  return proxyToBackend(request, '/alerts')
}
