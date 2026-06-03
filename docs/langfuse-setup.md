# Langfuse Local Setup (Option A: Run Locally per Developer)

This project uses Langfuse for observability (traces/spans).

To support **Option A** (everyone runs Langfuse on their own computer, persistently), each developer should run the provided `docker-compose.yml` locally. Langfuse data persists through Docker volumes.

## What you need
- Docker + Docker Compose
- A local `.env` (copy from `.env.example`)

## 1) Start Langfuse locally
From the repository root:

```console
make up
```

Wait ~30-60 seconds, then open:

```text
http://localhost:3000
```

## 2) Login (headless initialization)
This repository enables Langfuse **headless initialization** through `LANGFUSE_INIT_*` variables in `docker-compose.yml`.

Default init credentials (if you did not change `.env`):
- Email: `admin@example.com`
- Password: `adminadminadmin`

If you want different credentials, edit your local `.env` and set:
- `LANGFUSE_INIT_USER_EMAIL`
- `LANGFUSE_INIT_USER_PASSWORD`

Then recreate Langfuse:

```console
docker compose up -d --force-recreate langfuse
```

## 3) Verify the Project + API keys
After you login:
1. Open the project used by this repo (typically created on first startup).
2. Go to **Project settings / API keys**.
3. Confirm that the project has an API key pair matching the environment variables your app uses:
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`

In this repo, the `docker-compose.yml` headless init uses the app keys from `.env`:
- `LANGFUSE_INIT_PROJECT_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}`
- `LANGFUSE_INIT_PROJECT_SECRET_KEY=${LANGFUSE_SECRET_KEY}`

So if you keep the default `.env`, the keys should already match.

## 4) First trace sanity check
Start the full stack (so the chatbot backend can send traces):

```console
make up
```

Open the UI:
```text
http://localhost:8501
```

Send a message and check Langfuse for new traces/spans.

## 5) Manual alternative (if you disabled headless init)
If you removed `LANGFUSE_INIT_*` variables or your volumes already exist and you want to recreate resources manually:

1. Create an **Organization**
2. Create a **Project** (for example, `ProjetoEC`)
3. Create an **API key pair** for that project (public + secret)
4. Copy those values into your local `.env`:
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`

Then restart:
```console
make up
```

## Notes / troubleshooting
- If your browser can’t login or redirects unexpectedly, ensure you are using:
  - `http://localhost:3000` from the same machine that runs Docker.
- In a multi-machine scenario, `http://localhost:3000` on one machine is not the same server as `http://localhost:3000` on another.
- **`make eval` / Python on the host**: set `LANGFUSE_HOST=http://localhost:3000` in `.env`. The hostname `langfuse` only resolves inside the Docker network; the SDK also probes localhost automatically if the configured host is unreachable.
- **Langfuse logs: `NoSuchBucket` / S3 upload failed**: MinIO must have a bucket named `langfuse`. The `minio-init` service creates it on `docker compose up`. If you still see this error, run:

```console
docker compose run --rm minio-init
docker compose restart langfuse langfuse-worker
```