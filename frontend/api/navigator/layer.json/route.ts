/**
 * BFF: GET /api/navigator/layer.json
 * Returns MITRE ATT&CK Navigator layer for the current incident set.
 */

import { verifyJWT, unauthorizedResponse, proxyToBackend } from '../../../_lib/auth'

export async function GET(request: Request): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  return proxyToBackend(request, '/navigator/layer.json')
}
