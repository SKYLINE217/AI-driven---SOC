/**
 * BFF: POST /api/alerts/bulk-ack
 * POST /api/alerts/bulk-assign
 * Analyst+ can ack/assign.
 */

import {
  verifyJWT,
  unauthorizedResponse,
  proxyToBackend,
} from '../../../_lib/auth'

export async function POST(request: Request): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  // Extract action from URL
  const url = new URL(request.url)
  const action = url.pathname.endsWith('bulk-ack') ? 'bulk-ack' : 'bulk-assign'

  return proxyToBackend(request, `/alerts/${action}`)
}
