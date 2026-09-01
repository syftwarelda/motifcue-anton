# MotifCue Anton

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
- A local OpenAI-compatible Llama endpoint. Ollama works with the defaults in `.env.example`.
- The same `ANTON_INTERNAL_API_KEY` configured in MotifCue.
- An HTTPS location from which the final PDF can be reached.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Fill `.env`, then make sure the local models are available. With Ollama, for example:

```bash
ollama pull llama3.2
ollama pull llama3.2-vision:11b
```

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

## Report storage

`REPORT_STORAGE_DRIVER=local` writes `reports/<order-id>.pdf`. Set `REPORT_PUBLIC_BASE_URL` to the HTTPS base URL that serves this directory. This is convenient when a reverse proxy or storage mount already exposes the folder.

For S3-compatible storage, set `REPORT_STORAGE_DRIVER=s3` and fill the `S3_*` variables. The uploaded object is private unless your bucket or CDN policy exposes the configured public URL.

## Privacy and operations

- Logs contain order IDs and stages, never tokens, captions, email addresses, media URLs, or prompts.
- Downloaded images are placed under `data/orders/<order-id>` and removed after a successful report by default.
- The worker processes visual items with limited concurrency instead of sending an entire account to the model at once.
- Only the final structured summaries and numeric metrics are used for account-level synthesis.
- Failed orders receive a short machine-safe error code; private exception details remain local.

## Tests

```bash
pytest
ruff check .
```
