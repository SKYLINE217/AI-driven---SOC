# Scaling Path for SOC Triager

This document details the transition plan from the current MVP to a massive-scale enterprise deployment handling >1M EPS (Events Per Second).

## 1. Vercel to Dedicated API Gateway
Currently, the Vercel Edge Middleware and Serverless functions act as a BFF (Backend-For-Frontend) and API Gateway. While Vercel provides excellent global latency, a dedicated API Gateway (e.g., Kong, Ambassador, or AWS API Gateway) is recommended as the platform scales.
- **Why:** Centralized rate-limiting using global Redis (instead of Upstash over HTTP), strict TLS termination, and mTLS support for internal microservices.
- **Action:** Introduce an ingress controller in the Kubernetes cluster that handles JWT validation and routes directly to the FastAPI pods.

## 2. Serverless to Long-Running Containers
The Serverless BFF functions on Vercel are currently stateless and fast. However, for continuous WebSocket streaming and heavy backend proxying, long-running Node.js or Go containers will be more cost-effective.
- **Why:** Serverless execution time limits (e.g., 10s for hobby/pro) and cold starts can impact the real-time WebSocket experience if fallback polling is required.
- **Action:** Deploy the BFF as a Node.js Express/Fastify service within the K8s cluster, allowing persistent WebSocket connections directly between the browser and the BFF.

## 3. Playwright E2E and Cross-Browser CI Matrix
Currently, Playwright runs E2E tests against Chromium during the CI pipeline.
- **Why:** As the UI complexity grows (especially the D3/Mermaid Attack Graphs and real-time feeds), cross-browser compatibility becomes critical.
- **Action:** Expand the GitHub Actions CI matrix to run Playwright tests across WebKit (Safari), Firefox, and Mobile viewports before any merge to `main`. Use Playwright's sharding feature to parallelize the test execution and keep CI times under 3 minutes.

## 4. Kafka / Redpanda Partitioning
To handle >1M EPS, Redpanda topics must be partitioned aggressively.
- **Action:** Increase partition counts for `raw.*` and `normalized.events` from 4 to 64 or 128. Deploy the Faust workers in a Kubernetes Deployment with a Horizontal Pod Autoscaler (HPA) targeting 70% CPU utilization, allowing the consumer group to distribute the partition load dynamically.
