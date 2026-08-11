/**
 * BFF: POST /api/auth/login
 * Issues a JWT for demo/dev — in production replace with OIDC redirect.
 */

import { signJWT, type Role } from '../_lib/auth'

const DEMO_USERS: Record<Role, string> = {
  analyst: 'analyst@example.com',
  senior_analyst: 'senior@example.com',
  approver: 'approver@example.com',
}

export async function POST(request: Request): Promise<Response> {
  try {
    const body = await request.json() as { username?: string; role?: string }
    const { username, role } = body

    if (!role || !['analyst', 'senior_analyst', 'approver'].includes(role)) {
      return Response.json(
        { error: { code: 'BAD_REQUEST', message: 'Invalid role' } },
        { status: 400 }
      )
    }

    const typedRole = role as Role
    // In demo mode: accept any email for the given role
    const sub = username ?? DEMO_USERS[typedRole]

    const access_token = await signJWT(sub, typedRole)

    return Response.json({
      access_token,
      role: typedRole,
      email: sub,
      expires_in: 3600,
    })
  } catch {
    return Response.json(
      { error: { code: 'INTERNAL', message: 'Login failed' } },
      { status: 500 }
    )
  }
}
