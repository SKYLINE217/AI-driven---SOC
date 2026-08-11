import { jwtVerify } from 'jose'

export const config = {
  matcher: '/api/:path*',
}

export default async function middleware(req: Request) {
  const url = new URL(req.url)

  // Public routes
  if (url.pathname === '/api/auth/login') {
    return fetch(req)
  }

  const authHeader = req.headers.get('authorization')
  if (!authHeader?.startsWith('Bearer ')) {
    return Response.json({ error: { code: 'UNAUTHORIZED' } }, { status: 401 })
  }

  const token = authHeader.slice(7)
  const secret = process.env.JWT_SECRET

  if (!secret) {
    return Response.json({ error: { code: 'INTERNAL', message: 'Missing JWT_SECRET' } }, { status: 500 })
  }

  try {
    const encodedSecret = new TextEncoder().encode(secret)
    await jwtVerify(token, encodedSecret)
    
    // In a real implementation, you'd add rate limiting via Upstash Redis here
    
    return fetch(req) // Pass through to the API route
  } catch (err) {
    return Response.json({ error: { code: 'UNAUTHORIZED' } }, { status: 401 })
  }
}
