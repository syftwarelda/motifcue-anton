# MotifCue Anton

> Obsidian command reference: [Anton - Command Reference](docs/Anton%20-%20Command%20Reference.md)
>
> Knowledge system: [Anton - Knowledge RAG](docs/Anton%20-%20Knowledge%20RAG.md)

Anton is the private local worker that turns an authorized Instagram account into a useful creator report. It does not receive or decrypt Instagram tokens. MotifCue's backend keeps the token, calls Instagram, and exposes only the order data Anton needs through the private internal API.

## What it does

1. Claims the oldest paid order waiting in `PROCESSING`.
2. Asks MotifCue to validate the Instagram connection.
3. Downloads all available account and post data page by page.
4. Analyzes each post separately with the local vision model. Videos use their thumbnail in this first version; optional carousel children are supported when the backend returns them.
5. Calculates performance signals deterministically, then asks the text model to synthesize patterns and recommendations.
6. Creates a client-facing PDF, uploads or exposes it, and moves the order to `AWAITING_REVIEW`.

Local SQLite stores progress and per-post results, so restarting Anton does not repeat completed visual analysis.

## Requirements

- Python 3.12+
- Anton's local Qwen endpoint through the GPU scheduler on port `11435`.
- A separate OpenAI-compatible embedding endpoint. The included service runs Nomic on CPU.
- The same `ANTON_INTERNAL_API_KEY` configured in MotifCue.
- An HTTPS location from which the final PDF can be reached.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Fill `.env`. On Anton, Qwen remains behind the existing GPU scheduler. Install the dedicated
Nomic embedding model and service once:

```bash
mkdir -p ~/models/nomic-embed-text-v2-moe ~/.config/systemd/user
curl --fail --location --output ~/models/nomic-embed-text-v2-moe/nomic-embed-text-v2-moe.Q4_K_M.gguf \
  'https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe-GGUF/resolve/ffbcf4c99e5d617dda10ec8c0e9f75754b0cbb80/nomic-embed-text-v2-moe.Q4_K_M.gguf?download=true'
echo 'b5fb2811647b8ef461519a68a3bf67014a84a66a130c8a2af9413ff9f06d3f22  '"$HOME"'/models/nomic-embed-text-v2-moe/nomic-embed-text-v2-moe.Q4_K_M.gguf' | sha256sum --check
ln -sf "$PWD/deploy/systemd/user/motifcue-embeddings.service" \
  ~/.config/systemd/user/motifcue-embeddings.service
systemctl --user daemon-reload
systemctl --user enable --now motifcue-embeddings.service
```

This server binds only to `127.0.0.1:18083`, runs with `--n-gpu-layers 0`, and therefore does not
compete with Qwen for GPU memory or scheduler time.

If the staging deployment uses Vercel Deployment Protection, create a Protection Bypass for
Automation secret in Vercel and copy it into Anton's environment:

```bash
VERCEL_AUTOMATION_BYPASS_SECRET="your-vercel-bypass-secret"
```

Anton sends it only through the `x-vercel-protection-bypass` header. This is separate from
`ANTON_INTERNAL_API_KEY`; both protections remain active.

Run continuously:

```bash
anton run
```

Run using production configuration from `.env.prod`:

```bash
cp .env.prod.example .env.prod
anton run --prod
```

The flag also works with `anton once --prod` and `anton status --prod`. Development
and production settings remain separate, and neither `.env` nor `.env.prod` is committed.

Process at most one order and exit:

```bash
anton once
```

Check local state without exposing customer data:

```bash
anton status
```

Follow Anton's operational log in another terminal:

```bash
anton logs
```

`anton logs` starts with the latest 100 lines and continues following the file. Use
`anton logs --lines 250`, `anton logs --no-follow`, or `anton logs --prod` when needed.
The same events are shown in a colored console while Anton runs and written to
`logs/anton.log`. Files rotate automatically at 5 MB, keeping the five previous files.

`LOG_LEVEL=INFO` shows the useful production flow: claiming, validation, collection,
visual-analysis progress, synthesis, PDF creation, and completion. Temporarily use
`LOG_LEVEL=DEBUG` to include backend timings, cache decisions, individual media IDs,
and local-model request timings. Tokens, authorization headers, captions, prompts,
media URLs, and customer email addresses are never logged.

## Rebuild and export local order data

Anton keeps the Instagram snapshot, local AI analyses, synthesis and downloaded images by
default. This allows report design and analysis changes to be tested without claiming the order
again or calling MotifCue/Instagram.

Rebuild a PDF from one saved order:

```bash
anton regenerate ORDER_ID
```

The default output is `reports/ORDER_ID-local.pdf`. You can choose another path or language:

```bash
anton regenerate ORDER_ID --output reports/test-v2.pdf --language es
anton regenerate ORDER_ID --prod
```

Create a fresh account-level AI analysis from the saved data and cached visual findings:

```bash
anton reanalyze ORDER_ID
```

To also download the saved Instagram thumbnails again and rerun every available image through
the local vision model:

```bash
anton reanalyze ORDER_ID --refresh-images
```

The default output is `reports/ORDER_ID-reanalyzed.pdf`. Both variants are local-only: they do not
claim an order, call MotifCue's internal API, or change the remote order status. Saved Instagram
media URLs can expire; when a refresh fails, Anton retains the previous local image and cached
visual analysis instead of replacing them with an empty result.

Export everything Anton has locally for an order into one readable JSON file:

```bash
anton export ORDER_ID
anton export ORDER_ID --output exports/order-debug.json
```

The export contains the persisted Instagram payload, each raw paginated endpoint response saved
during collection, local job metadata, account synthesis, per-media analyses and a local
media-file manifest. Older orders collected before this feature include the consolidated snapshot
but may not have the individual response pages. The file may contain customer captions and media
URLs, so share it privately. It never contains an Instagram token because Anton never receives
one.

Keep `CLEANUP_MEDIA_AFTER_SUCCESS=false` to preserve thumbnails for offline regeneration. Setting
it to `true` removes only downloaded media after success; the snapshot, database and analyses are
still retained.

## Local knowledge RAG

Anton can maintain an approved, versioned knowledge library and retrieve relevant excerpts during
account synthesis. The source content, chunks and embeddings remain in Anton's local SQLite
database. Embeddings are generated by the dedicated CPU-only llama.cpp service with multilingual
`nomic-embed-text-v2-moe`; Qwen remains responsible for image analysis and report synthesis.

Download or update the official source catalog and build the semantic index:

```bash
anton knowledge sync
```

Inspect the library and test retrieval:

```bash
anton knowledge status
anton knowledge search "Reels opening frame and retention"
```

The first revision of each built-in official source becomes active. If its content later changes,
the new revision remains pending and the previous approved revision stays active. Review the
change, then approve it explicitly:

```bash
anton knowledge diff SOURCE_ID
anton knowledge approve SOURCE_ID
```

Only active approved revisions are available to report generation. If the embedding service is
unavailable, synchronization still stores the source and Anton falls back to lexical
retrieval instead of blocking report generation.

## Report storage

`REPORT_STORAGE_DRIVER=local_only` is the default. It writes `reports/<order-id>.pdf`,
does not upload it anywhere, and moves the order to `AWAITING_REVIEW` without a report URL.

`REPORT_STORAGE_DRIVER=local` also writes the PDF locally, but expects
`REPORT_PUBLIC_BASE_URL` to be an HTTPS location that already serves that directory.

For S3-compatible storage, set `REPORT_STORAGE_DRIVER=s3` and fill the `S3_*` variables. The uploaded object is private unless your bucket or CDN policy exposes the configured public URL.

## Privacy and operations

- Logs contain order IDs and stages, never tokens, captions, email addresses, media URLs, or prompts.
- Downloaded images are placed under `data/orders/<order-id>` and retained by default for local regeneration.
- The worker processes visual items with limited concurrency instead of sending an entire account to the model at once.
- Only the final structured summaries and numeric metrics are used for account-level synthesis.
- Failed orders receive a short machine-safe error code; private exception details remain local.

## Tests

```bash
pytest
ruff check .
```
