/**
 * BFF: GET /api/incidents/:id
 * POST /api/incidents/:id/status   — Analyst: ack only; Senior+: escalate/close
 * POST /api/incidents/:id/approve  — Approver only
 * GET  /api/incidents/:id/timeline
 * GET  /api/incidents/:id/ledger
 * GET  /api/incidents/:id/report.md
 * GET  /api/incidents/:id/graph.mmd
 * GET  /api/incidents/:id/playbook
 */

import {
  verifyJWT,
  requireRole,
  unauthorizedResponse,
  forbiddenResponse,
  proxyToBackend,
} from '../../../_lib/auth'

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  const url = new URL(request.url)
  // Strip the /api prefix and replace dynamic segment
  const backendPath = url.pathname.replace('/api', '')
  return proxyToBackend(request, backendPath)
}

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
): Promise<Response> {
  const claims = await verifyJWT(request.headers.get('authorization'))
  if (!claims) return unauthorizedResponse()

  const url = new URL(request.url)
  const pathParts = url.pathname.split('/')
  const action = pathParts[pathParts.length - 1] // 'status', 'approve', etc.

  if (action === 'approve') {
    // Approver only
    if (!requireRole(claims, 'approver')) {
      return forbiddenResponse('Only Approvers can approve playbooks')
    }
  } else if (action === 'status') {
    // Analyst can only ack; Senior+ can do more — validated by backend too
    if (!requireRole(claims, 'analyst')) {
      return forbiddenResponse()
    }
  }

  const backendPath = url.pathname.replace('/api', '')
  return proxyToBackend(request, backendPath)
}
