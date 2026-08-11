# Load Test Results

## k6 Load Test Summary

**Target:** `GET /api/alerts` (Vercel Serverless BFF -> FastAPI Backend)
**Auth:** Valid Analyst JWT Bearer Token
**Duration:** 2m
**Virtual Users (VUs):** 50

### Metrics
| Metric | Value |
|--------|-------|
| Request Count | 12,430 |
| HTTP Failures | 0.00% (0) |
| Avg Latency | 45.2 ms |
| p50 Latency | 41.8 ms |
| p95 Latency | 89.4 ms |
| Data Received | 15.4 MB |

### Analysis
The Vercel BFF securely processes and proxies requests to the backend with minimal overhead. The backend easily sustains 100+ requests per second without significant queuing delays. Rate limiting in the Edge Middleware (using Upstash Redis) was tested separately and successfully throttled requests exceeding 100/sec per IP, returning HTTP 429.
