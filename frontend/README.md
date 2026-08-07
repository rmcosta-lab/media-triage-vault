# Local Media Organizer — frontend

Next.js + TypeScript UI for the local, offline `media-organizer` backend
(`specs/tech-stack.md`, roadmap Stage G). Talks only to
`http://127.0.0.1:<port>` — see `NEXT_PUBLIC_API_BASE_URL` below.

## Prerequisites

- The backend running locally: `uv run media-organizer serve` (defaults
  to port 8000) from the repo root.

## Development

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000.

If the backend is running on a non-default port, set
`NEXT_PUBLIC_API_BASE_URL` (e.g. in `.env.local`):

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Other commands

```bash
pnpm build   # production build
pnpm start   # run the production build
pnpm lint    # eslint
```
