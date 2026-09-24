"""
Step 6: Parse the HTML response to JSON and CSV

Reads the HTML saved by step 4 (ScrapeOps Proxy API) or step 5 (Botasaurus)
and extracts site-specific fields.

Usage:
  python 6_parse_html_response.py -t fbref
  python 6_parse_html_response.py -t sportsdirect
  python 6_parse_html_response.py -t hepsiburada
"""

import csv
import json
import re
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup

from helpers import (
    OUTPUT_DIR,
    RESPONSES_DIR,
    ensure_dirs,
    is_cloudflare_blocked,
    parse_target_arg,
)

# Prefer the richest HTML sources first.
HTML_CANDIDATES = (
    "4_scrapeops_cloudflare_level_2.html",
    "5_botasaurus_residential.html",
    "4_scrapeops_cloudflare_level_1.html",
    "4_scrapeops_default.html",
)

SCORE_RE = re.compile(r"^\d+\s*[–\-]\s*\d+$")
MATCH_SLUG_RE = re.compile(
    r"^/en/matches/[0-9a-f]+/"
    r"(?P<body>.+?)-"
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)-"
    r"(?P<day>\d{1,2})-(?P<year>\d{4})-"
    r"(?P<comp>.+)$",
    re.IGNORECASE,
)


def find_html(target_key: str) -> Path:
    folder = RESPONSES_DIR / target_key
    for name in HTML_CANDIDATES:
        path = folder / name
        if path.exists() and path.stat().st_size > 1000:
            return path

    for name in HTML_CANDIDATES:
        path = RESPONSES_DIR / name
        if path.exists() and path.stat().st_size > 1000:
            return path

    raise FileNotFoundError(
        f"No HTML found for target '{target_key}'.\n"
        f"Expected one of: {', '.join(HTML_CANDIDATES)} under {folder}\n"
        "Run step 4 or 5 first."
    )


def load_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def abs_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"https://fbref.com{href}"


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(" ", strip=True)
            if text:
                return text
    return ""


def meta_content(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def clean_team_name(name: str) -> str:
    # FBref often prefixes country flags as short codes, e.g. "ma Morocco"
    return re.sub(r"^[a-z]{2}\s+", "", name.strip())


def slug_to_title(slug: str) -> str:
    return unquote(slug).replace("-", " ").strip()


def parse_match_slug(href: str) -> dict[str, str] | None:
    path = href.split("?")[0]
    match = MATCH_SLUG_RE.match(path)
    if not match:
        return None

    body = match.group("body")
    # Body is "Home-Away" with hyphenated names; split on the middle-most hyphen
    # is imperfect, so keep teams as a pair string if needed.
    parts = body.split("-")
    if len(parts) < 2:
        return None

    # Heuristic: last token(s) for away are hard; prefer even-ish split.
    # Better: use known pattern HomeTeam-AwayTeam where both are Title-Case words.
    # Split at the first occurrence of a capitalised second team is not available
    # in slug form. Use midpoint on hyphen tokens.
    mid = len(parts) // 2
    home = slug_to_title("-".join(parts[:mid]))
    away = slug_to_title("-".join(parts[mid:]))
    date = f"{match.group('month')} {match.group('day')}, {match.group('year')}"
    competition = slug_to_title(match.group("comp"))

    return {
        "home": home,
        "away": away,
        "date": date,
        "competition": competition,
    }


def parse_matches_from_game_summaries(soup: BeautifulSoup) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    seen: set[str] = set()

    for game in soup.select(".game_summary"):
        team_links = game.select('a[href*="/en/squads/"]')
        score_link = game.select_one('a[href*="/en/matches/"]')
        if len(team_links) < 2 or not score_link:
            continue

        href = score_link.get("href", "").strip()
        if not href or href in seen:
            continue
        seen.add(href)

        competition = ""
        heading = game.find_parent("div", class_="fb_matches")
        if heading:
            h4 = heading.find_previous("h4")
            if h4:
                competition = clean_team_name(h4.get_text(" ", strip=True))

        slug_meta = parse_match_slug(href) or {}
        matches.append(
            {
                "home": team_links[0].get_text(strip=True),
                "score": score_link.get_text(strip=True),
                "away": team_links[1].get_text(strip=True),
                "competition": competition or slug_meta.get("competition", ""),
                "date": slug_meta.get("date", ""),
                "match_url": abs_url(href),
                "home_url": abs_url(team_links[0].get("href", "")),
                "away_url": abs_url(team_links[1].get("href", "")),
            }
        )

    return matches


def parse_matches_from_score_links(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Fallback when .game_summary markup is missing (collapsed nav HTML)."""
    matches: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/en/matches/"]'):
        score = link.get_text(strip=True)
        href = link.get("href", "").strip()
        if not href or href in seen or not SCORE_RE.match(score):
            continue
        seen.add(href)

        slug_meta = parse_match_slug(href)
        if not slug_meta:
            continue

        matches.append(
            {
                "home": slug_meta["home"],
                "score": score.replace("-", "–"),
                "away": slug_meta["away"],
                "competition": slug_meta["competition"],
                "date": slug_meta["date"],
                "match_url": abs_url(href),
                "home_url": "",
                "away_url": "",
            }
        )

    return matches


def parse_leagues(soup: BeautifulSoup) -> list[dict[str, str]]:
    leagues: list[dict[str, str]] = []
    seen: set[str] = set()

    for section_id, gender in (
        ("leagues_primary", "men"),
        ("leagues_secondary", "women"),
    ):
        section = soup.select_one(f"#{section_id}")
        if not section:
            continue

        for card in section.select('[id^="mini-"]'):
            country_link = card.select_one('h2 a[href*="/country/"]')
            country = (
                country_link.get_text(strip=True)
                if country_link
                else card.select_one("h2").get_text(" ", strip=True)
                if card.select_one("h2")
                else ""
            )
            country = clean_team_name(country)

            # Main competition link in the card intro paragraph
            comp_link = card.select_one('p a[href*="/comps/"]')
            if not comp_link:
                continue

            href = comp_link.get("href", "").strip()
            if not href or href in seen:
                continue
            seen.add(href)

            name = re.sub(
                r"^\d{4}(?:-\d{4})?\s+",
                "",
                comp_link.get_text(" ", strip=True),
            )
            name = re.sub(r"\s+Table, Stats & Results$", "", name).strip()

            leagues.append(
                {
                    "name": name,
                    "country": country,
                    "gender": gender,
                    "url": abs_url(href),
                }
            )

    # Fallback: any unique /comps/ league stats links
    if not leagues:
        for link in soup.select('a[href*="/comps/"]'):
            href = link.get("href", "").strip()
            name = link.get_text(strip=True)
            if (
                not href
                or not name
                or href in seen
                or "/schedule/" in href
                or "/stats/" in href
            ):
                continue
            if not re.search(r"/comps/[^/]+/[^/]+-Stats/?$", href):
                continue
            seen.add(href)
            leagues.append(
                {
                    "name": name,
                    "country": "",
                    "gender": "",
                    "url": abs_url(href),
                }
            )

    return leagues


def parse_standings(soup: BeautifulSoup) -> list[dict[str, str]]:
    standings: list[dict[str, str]] = []

    for table in soup.select("table.stats_table"):
        headers = [th.get("data-stat") or th.get_text(strip=True) for th in table.select("thead th")]
        if "team" not in headers and "Squad" not in [
            th.get_text(strip=True) for th in table.select("thead th")
        ]:
            continue

        caption = table.select_one("caption")
        table_name = caption.get_text(strip=True) if caption else table.get("id", "")
        table_name = re.sub(r"\s+Table$", "", table_name)

        # Prefer nearby country/league heading from mini cards
        card = table.find_parent("div", id=re.compile(r"^mini-"))
        competition = table_name
        if card and card.select_one("p a"):
            competition = re.sub(
                r"^\d{4}(?:-\d{4})?\s+",
                "",
                card.select_one("p a").get_text(" ", strip=True),
            )
            competition = re.sub(r"\s+Table, Stats & Results$", "", competition).strip()
            if table_name and table_name not in competition:
                competition = f"{competition} — {table_name}"

        for row in table.select("tbody tr"):
            if row.get("class") and "spacer" in row.get("class", []):
                continue

            cells = {
                (cell.get("data-stat") or f"col_{i}"): cell.get_text(" ", strip=True)
                for i, cell in enumerate(row.select("th, td"))
            }
            team = clean_team_name(cells.get("team", ""))
            if not team or team.lower() in {"squad", "team"}:
                continue

            team_link = row.select_one('a[href*="/squads/"]')
            standings.append(
                {
                    "competition": competition,
                    "rank": cells.get("rank") or cells.get("ranker", ""),
                    "team": team,
                    "played": cells.get("games", ""),
                    "wins": cells.get("wins", ""),
                    "draws": cells.get("ties", ""),
                    "losses": cells.get("losses", ""),
                    "goal_diff": cells.get("goal_diff", ""),
                    "points": cells.get("points") or cells.get("points_per_game", ""),
                    "team_url": abs_url(team_link.get("href", "")) if team_link else "",
                }
            )

    return standings


def parse_fbref(soup: BeautifulSoup, source_url: str) -> dict:
    matches = parse_matches_from_game_summaries(soup)
    if not matches:
        matches = parse_matches_from_score_links(soup)

    leagues = parse_leagues(soup)
    standings = parse_standings(soup)
    title = soup.title.get_text(strip=True) if soup.title else ""

    return {
        "source_url": source_url,
        "page_title": title,
        "league_count": len(leagues),
        "match_count": len(matches),
        "standing_row_count": len(standings),
        "leagues": leagues,
        "matches": matches,
        "standings": standings,
    }


def parse_product(soup: BeautifulSoup, source_url: str, site: str) -> dict:
    title = (
        meta_content(soup, "og:title", "twitter:title")
        or first_text(
            soup,
            [
                "h1",
                "[data-testid='product-name']",
                "[data-test-id='product-name']",
                ".product-title",
                "#product-title",
                ".productName",
            ],
        )
        or (soup.title.get_text(strip=True) if soup.title else "")
    )

    price = (
        meta_content(soup, "product:price:amount", "og:price:amount")
        or first_text(
            soup,
            [
                "[itemprop='price']",
                "[data-testid='price']",
                ".price",
                ".product-price",
                "#product-price",
                ".priceTag",
            ],
        )
    )
    if not price:
        match = re.search(r"(£|€|\$|₺)\s?\d+[.,]?\d*", soup.get_text(" ", strip=True))
        price = match.group(0) if match else ""

    description = meta_content(soup, "og:description", "description")
    image = meta_content(soup, "og:image")
    brand = meta_content(soup, "product:brand", "brand") or first_text(
        soup, ["[itemprop='brand']", ".brand", ".product-brand"]
    )

    return {
        "source_url": source_url,
        "site": site,
        "page_title": soup.title.get_text(strip=True) if soup.title else "",
        "product_name": title,
        "brand": brand,
        "price": price,
        "description": description[:500] if description else "",
        "image_url": image,
    }


def save_json(filename: str, data: object) -> Path:
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved JSON to: {path}")
    return path


def save_csv(filename: str, rows: list[dict[str, str]]) -> Path:
    path = OUTPUT_DIR / filename
    if not rows:
        path.write_text("", encoding="utf-8")
        print(f"  Saved empty CSV to: {path}")
        return path

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved CSV to:  {path}")
    return path


def main() -> None:
    ensure_dirs()
    target_key, target_url = parse_target_arg("Step 6: parse HTML")
    print(f"Target: {target_key}")

    html_path = find_html(target_key)
    print(f"Parsing {html_path}...")

    html = load_html(html_path)
    if is_cloudflare_blocked(html):
        raise ValueError(
            "The HTML file still contains a Cloudflare challenge page. "
            "Re-run step 4 or 5 with a working bypass."
        )

    soup = BeautifulSoup(html, "lxml")

    if target_key == "fbref":
        page_data = parse_fbref(soup, target_url)
        print(f"\nParsed page title: {page_data['page_title']}")
        print(f"  Leagues found:   {page_data['league_count']}")
        print(f"  Matches found:   {page_data['match_count']}")
        print(f"  Standing rows:   {page_data['standing_row_count']}")
        if page_data["matches"]:
            sample = page_data["matches"][0]
            print(
                f"  Sample match:    {sample['home']} {sample['score']} {sample['away']}"
                f" ({sample['competition']})"
            )

        save_json(f"{target_key}_homepage.json", page_data)
        save_csv(f"{target_key}_leagues.csv", page_data["leagues"])
        save_csv(f"{target_key}_matches.csv", page_data["matches"])
        save_csv(f"{target_key}_standings.csv", page_data["standings"])
        return

    page_data = parse_product(soup, target_url, site=target_key)
    print(f"\nParsed product: {page_data['product_name']}")
    print(f"  Price: {page_data['price'] or '(not found)'}")
    print(f"  Brand: {page_data['brand'] or '(not found)'}")

    save_json(f"{target_key}_product.json", page_data)
    save_csv(f"{target_key}_product.csv", [page_data])


if __name__ == "__main__":
    main()
