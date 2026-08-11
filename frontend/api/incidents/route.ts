/**
 * BFF: GET /api/incidents
 * All roles can list incidents.
 */

import { verifyJWT, unauthorizedResponse, proxyToBackend } from '../../_lib/auth'

export async function GET(request: Request): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  return proxyToBackend(request, '/incidents')
}
