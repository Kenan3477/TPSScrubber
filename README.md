# TPS Scrubber

A small portal that uploads a list of UK phone numbers, counts them, then checks each one against the public Telephone Preference Service **Am I Registered?** page.

It opens the page, types a number, clicks **Check my number**, reads the result, then loads the page again for the next number.

This uses the public one-number checker. It is not a licensed DMA TPS file. The site can rate-limit bulk checks.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Use

1. Upload a CSV, TXT, or Excel file.
2. Review how many numbers are valid, invalid, or duplicated.
3. Click **Run TPS Scan**.
4. Download `on_tps.csv` and `not_on_tps.csv` when it finishes.

Numbers should include the leading zero. Spaces, `+44`, and `44` prefixes are cleaned automatically.

## Settings

- `TPS_DELAY_SECONDS` — pause between checks (default `3.5`)
- `TPS_HEADED=1` — show the browser window while it works

## Tests

```bash
pytest -q
```
