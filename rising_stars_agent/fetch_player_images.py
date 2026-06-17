import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen


INPUT_FILE = Path("players.csv")
OUTPUT_DIR = Path("player_images")
MANIFEST_CSV = OUTPUT_DIR / "manifest.csv"
MANIFEST_JSON = OUTPUT_DIR / "manifest.json"
INDEX_FILE = OUTPUT_DIR / "index.md"
HTML_INDEX_FILE = OUTPUT_DIR / "index.html"

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "fifasprint-rising-stars-demo/1.0"
REQUEST_DELAY_SECONDS = 1.0

PAGE_TITLE_OVERRIDES = {
    "Kylian Mbappé": "Kylian Mbappé",
    "Xavi Simons": "Xavi Simons",
    "Alejandro Garnacho": "Alejandro Garnacho",
    "Nuno Mendes": "Nuno Mendes (footballer)",
    "William Saliba": "William Saliba",
    "Sandro Tonali": "Sandro Tonali",
}


def load_player_names(filepath):
    with open(filepath, newline="", encoding="utf-8") as csvfile:
        return [row["name"] for row in csv.DictReader(csvfile)]


def clean_text(value):
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def safe_filename(value):
    normalized = value.lower()
    normalized = normalized.replace("é", "e")
    normalized = normalized.replace("ã", "a")
    normalized = normalized.replace("ñ", "n")
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def request_json(url, params):
    time.sleep(REQUEST_DELAY_SECONDS)
    request_url = f"{url}?{urlencode(params)}"
    request = Request(request_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url, filepath):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        filepath.write_bytes(response.read())


def find_player_page(player_name):
    title_override = PAGE_TITLE_OVERRIDES.get(player_name)
    if title_override:
        payload = request_json(
            WIKIPEDIA_API_URL,
            {
                "action": "query",
                "titles": title_override,
                "prop": "pageimages|info",
                "pithumbsize": 800,
                "piprop": "thumbnail|name|original",
                "inprop": "url",
                "format": "json",
                "formatversion": 2,
            },
        )
        pages = payload.get("query", {}).get("pages", [])
        if pages and not pages[0].get("missing"):
            return pages[0]

    payload = request_json(
        WIKIPEDIA_API_URL,
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"{player_name} footballer",
            "gsrlimit": 1,
            "prop": "pageimages|info",
            "pithumbsize": 800,
            "piprop": "thumbnail|name|original",
            "inprop": "url",
            "format": "json",
            "formatversion": 2,
        },
    )
    pages = payload.get("query", {}).get("pages", [])
    return pages[0] if pages else None


def fetch_image_info(page):
    image_name = page.get("pageimage")
    if not image_name:
        return None

    payload = request_json(
        WIKIPEDIA_API_URL,
        {
            "action": "query",
            "titles": f"File:{image_name}",
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": 800,
            "format": "json",
            "formatversion": 2,
        },
    )
    pages = payload.get("query", {}).get("pages", [])
    if not pages or not pages[0].get("imageinfo"):
        return None
    return pages[0]["imageinfo"][0]


def extension_for_image(image_url, mime_type):
    suffix = Path(urlparse(image_url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    return ".jpg"


def metadata_value(extmetadata, key):
    item = extmetadata.get(key, {})
    return clean_text(item.get("value", ""))


def fetch_player_image(player_name):
    page = find_player_page(player_name)
    if not page:
        return {"player": player_name, "status": "no_wikipedia_page"}

    image_info = fetch_image_info(page)
    if not image_info:
        return {
            "player": player_name,
            "status": "no_page_image",
            "wikipedia_page": page.get("fullurl", ""),
        }

    image_url = image_info.get("thumburl") or image_info.get("url")
    mime_type = image_info.get("mime", "")
    extension = extension_for_image(image_url, mime_type)
    local_path = OUTPUT_DIR / f"{safe_filename(player_name)}{extension}"
    download_file(image_url, local_path)

    extmetadata = image_info.get("extmetadata", {})
    return {
        "player": player_name,
        "status": "downloaded",
        "local_path": str(local_path),
        "wikipedia_page": page.get("fullurl", ""),
        "image_url": image_url,
        "artist": metadata_value(extmetadata, "Artist"),
        "credit": metadata_value(extmetadata, "Credit"),
        "license": metadata_value(extmetadata, "LicenseShortName"),
        "license_url": metadata_value(extmetadata, "LicenseUrl"),
        "attribution_required": metadata_value(extmetadata, "AttributionRequired"),
    }


def load_existing_manifest():
    if not MANIFEST_CSV.exists():
        return {}

    with open(MANIFEST_CSV, newline="", encoding="utf-8") as csvfile:
        rows = csv.DictReader(csvfile)
        return {row["player"]: row for row in rows}


def local_image_fallback(player_name, existing_manifest):
    existing_row = existing_manifest.get(player_name)
    if existing_row and Path(existing_row.get("local_path", "")).exists():
        return existing_row

    filename_stem = safe_filename(player_name)
    for extension in [".jpg", ".png", ".webp"]:
        local_path = OUTPUT_DIR / f"{filename_stem}{extension}"
        if local_path.exists():
            return {
                "player": player_name,
                "status": "downloaded",
                "local_path": str(local_path),
                "wikipedia_page": "",
                "image_url": "",
                "artist": "",
                "credit": "Local image already downloaded; rerun later to refresh source metadata.",
                "license": "",
                "license_url": "",
                "attribution_required": "",
            }

    return None


def write_manifest(rows):
    fieldnames = [
        "player",
        "status",
        "local_path",
        "wikipedia_page",
        "image_url",
        "artist",
        "credit",
        "license",
        "license_url",
        "attribution_required",
    ]

    with open(MANIFEST_CSV, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    MANIFEST_JSON.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_index(rows):
    lines = [
        "# Rising Star Player Images",
        "",
        "Images were fetched from Wikipedia/Wikimedia where available. Check `manifest.csv` for source and license metadata.",
        "",
    ]
    for row in rows:
        if row.get("status") == "downloaded" and row.get("local_path"):
            local_name = Path(row["local_path"]).name
            lines.extend(
                [
                    f"## {row['player']}",
                    f"![{row['player']}]({local_name})",
                    f"- Source page: {row.get('wikipedia_page', '')}",
                    f"- License: {row.get('license', '')}",
                    f"- Credit: {row.get('artist') or row.get('credit') or 'See manifest'}",
                    "",
                ]
            )
        else:
            lines.extend([f"## {row['player']}", f"- Image status: {row['status']}", ""])

    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")


def write_html_index(rows):
    cards = []
    for row in rows:
        player = html.escape(row["player"])
        if row.get("status") == "downloaded" and row.get("local_path"):
            local_name = html.escape(Path(row["local_path"]).name)
            license_name = html.escape(row.get("license", ""))
            credit = html.escape(row.get("artist") or row.get("credit") or "See manifest")
            source = html.escape(row.get("wikipedia_page", ""))
            cards.append(
                f"""
                <article class="card">
                  <img src="{local_name}" alt="{player}">
                  <div class="body">
                    <h2>{player}</h2>
                    <p>{license_name}</p>
                    <p>{credit}</p>
                    <a href="{source}">Source</a>
                  </div>
                </article>
                """
            )
        else:
            status = html.escape(row.get("status", "missing"))
            cards.append(
                f"""
                <article class="card missing">
                  <div class="placeholder">{player}</div>
                  <div class="body">
                    <h2>{player}</h2>
                    <p>{status}</p>
                  </div>
                </article>
                """
            )

    html_content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rising Star Player Images</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f2;
      color: #1e2428;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
    }}
    .subhead {{
      margin: 0 0 24px;
      color: #52606b;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 16px;
    }}
    .card {{
      overflow: hidden;
      border: 1px solid #d8d8d2;
      border-radius: 8px;
      background: #ffffff;
    }}
    img, .placeholder {{
      width: 100%;
      aspect-ratio: 4 / 5;
      object-fit: cover;
      display: block;
      background: #dfe4e7;
    }}
    .placeholder {{
      display: grid;
      place-items: center;
      padding: 16px;
      box-sizing: border-box;
      text-align: center;
      font-weight: 700;
      color: #52606b;
    }}
    .body {{
      padding: 12px;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 17px;
    }}
    p {{
      margin: 4px 0;
      font-size: 13px;
      color: #52606b;
    }}
    a {{
      display: inline-block;
      margin-top: 8px;
      color: #0f5f7a;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Rising Star Player Images</h1>
    <p class="subhead">Fetched from Wikipedia/Wikimedia where available. See manifest.csv for source and license metadata.</p>
    <section class="grid">
      {''.join(cards)}
    </section>
  </main>
</body>
</html>
"""
    HTML_INDEX_FILE.write_text(html_content, encoding="utf-8")


def main():
    if not INPUT_FILE.exists():
        print(f"Missing input file: {INPUT_FILE}")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    rows = []
    existing_manifest = load_existing_manifest()

    for player_name in load_player_names(INPUT_FILE):
        print(f"Fetching image for {player_name}...")
        fallback = local_image_fallback(player_name, existing_manifest)
        if fallback and fallback.get("status") == "downloaded":
            rows.append(fallback)
            continue

        try:
            rows.append(fetch_player_image(player_name))
        except (HTTPError, URLError, TimeoutError) as error:
            fallback = local_image_fallback(player_name, existing_manifest)
            if fallback:
                rows.append(fallback)
            else:
                rows.append(
                    {
                        "player": player_name,
                        "status": f"error: {error}",
                    }
                )

    write_manifest(rows)
    write_index(rows)
    write_html_index(rows)
    downloaded = sum(1 for row in rows if row.get("status") == "downloaded")
    print(f"Downloaded {downloaded}/{len(rows)} player images into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
