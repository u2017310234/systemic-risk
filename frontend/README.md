# Frontend v2.4

From this directory, run `npm ci && npm run dev`. The checked-in default is a labeled historical reconstruction dated 2025-05-16.

- `npm run build && npm start`: regular Next.js server.
- `npm run build:cloudflare`: static pages in `out/`, including all declared bank routes; the Worker handles MCP, status and data headers.
- `npx wrangler deploy --dry-run`: validate the bundle without deploying.
- `npx wrangler deploy`: deploy to your configured Cloudflare account.

Workers Git integration: root `frontend`, build `npm ci && npm run build:cloudflare`, deploy `npx wrangler deploy`. Set `MCP_ORIGIN_URL` to the Python server base URL (for example `https://your-backend.example`). The backend must trust its own hostname in `MCP_ALLOWED_HOSTS`. Without an origin, the website still displays data; `/mcp` returns explicit HTTP 503.

`DATA_SOURCE_DIR` overrides repository `../data` during build. It resolves `current.json`, rejects incompatible or mixed snapshots, and copies only the committed batch. Static data updates require a new frontend build/deployment. No production account or domain is assumed by the build.
