/**
 * BFF Auth Library — JWT signing, verification, role hierarchy
 * Runs in Vercel Serverless (Node.js runtime), NEVER in the browser bundle.
 */

import { SignJWT, jwtVerify, type JWTPayload } from 'jose'

export type Role = 'analyst' | 'senior_analyst' | 'approver'

export interface JWTClaims extends JWTPayload {
  sub: string
  role: Role
}

const ROLE_HIERARCHY: Record<Role, Role[]> = {
  analyst: ['analyst'],
  senior_analyst: ['analyst', 'senior_analyst'],
  approver: ['analyst', 'senior_analyst', 'approver'],
}

function getSecret(): Uint8Array {
  const secret = process.env.JWT_SECRET
  if (!secret) throw new Error('JWT_SECRET environment variable is not set')
  return new TextEncoder().encode(secret)
}

/** Issue a signed JWT with 1-hour expiry */
export async function signJWT(sub: string, role: Role): Promise<string> {
  return new SignJWT({ sub, role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('1h')
    .sign(getSecret())
}

/** Verify and decode a JWT from an Authorization header. Returns null on failure. */
export async function verifyJWT(
  authHeader: string | null | undefined
): Promise<JWTClaims | null> {
  if (!authHeader?.startsWith('Bearer ')) return null
  try {
    const { payload } = await jwtVerify(authHeader.slice(7), getSecret())
    if (!payload.sub || !payload.role) return null
    return payload as JWTClaims
  } catch {
    return null
  }
}

/** Check if claims include the required role (using hierarchy) */
export function requireRole(claims: JWTClaims, ...roles: Role[]): boolean {
  const effective = ROLE_HIERARCHY[claims.role] ?? []
  return roles.some((r) => effective.includes(r))
}

/** Standard 401 response */
export function unauthorizedResponse() {
  return Response.json(
    { error: { code: 'UNAUTHORIZED', message: 'Invalid or missing JWT' } },
    { status: 401 }
  )
}

/** Standard 403 response */
export function forbiddenResponse(reason = 'Insufficient role') {
  return Response.json(
    { error: { code: 'FORBIDDEN', message: reason } },
    { status: 403 }
  )
}

/** Proxy a request to the backend, forwarding auth and body */
export async function proxyToBackend(
  request: Request,
  backendPath: string,
  options?: RequestInit
): Promise<Response> {
  const backendUrl = process.env.BACKEND_API_URL ?? 'http://localhost:8000'
  const url = new URL(request.url)
  const targetUrl = `${backendUrl}${backendPath}${url.search}`

  const headers = new Headers(request.headers)
  headers.set('X-Internal-Token', process.env.INTERNAL_SERVICE_TOKEN ?? '')
  // Strip the client's Host header to avoid issues
  headers.delete('host')

  const isBodyMethod = ['POST', 'PUT', 'PATCH'].includes(request.method)

  return fetch(targetUrl, {
    method: request.method,
    headers,
    body: isBodyMethod ? request.body : undefined,
    // @ts-expect-error - duplex is needed for streaming bodies in Node
    duplex: isBodyMethod ? 'half' : undefined,
    ...options,
  })
}
