# Frontend

Standalone frontend workspace for the Systemic Risk UI.

## Run

```bash
cd frontend
npm install
npm run dev
```

The frontend syncs repository data from `../data` into `frontend/public/data` before dev/build.

## Deploy

For Vercel or Cloudflare, set the project root directory to `frontend/`.

## Structure

- `app/` Next.js routes
- `components/` UI components
- `lib/` types, formatters, adapters, graph logic
- `scripts/sync-data.mjs` copies root data into the frontend workspace
