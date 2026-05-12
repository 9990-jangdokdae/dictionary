from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from scrapling.fetchers import DynamicFetcher, Fetcher
from scrapling.parser import Selector

from stock_dictionary.models import RawTerm, ScrapeFailure


DynamicScraper = Callable[[str, str], list[RawTerm]]

KB_THEME_LABELS = [
    "기본용어",
    "주문",
    "시장제도",
    "투자자",
    "내계좌",
    "기술적분석",
    "기본적분석",
    "전문용어",
    "재무제표",
    "주가변동요인",
    "ETF",
    "펀드",
    "채권",
    "ELS/DLS",
    "신용/대출",
    "CMA/RP/발행어음",
    "ETN",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _clean_html_fragment(html: str) -> str:
    return _clean_text(" ".join(Selector(f"<div>{html}</div>").css("::text").getall()))


def _split_title_definition(text: str) -> tuple[str, str]:
    lines = [_clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 2:
        return "", ""
    return lines[0], _clean_text(" ".join(lines[1:]))


def _raw_term(term: str, definition: str, source_name: str, source_url: str, collected_at: str) -> RawTerm | None:
    term = _clean_text(term)
    definition = _clean_text(definition)
    if not term or not definition:
        return None
    return RawTerm(
        term=term,
        raw_definition=definition,
        source_name=source_name,
        source_url=source_url,
        collected_at=collected_at,
    )


def extract_terms_from_html(html: str, source_name: str, source_url: str) -> list[RawTerm]:
    page = Selector(html)
    collected_at = _now_iso()
    rows: list[RawTerm] = []

    for card in page.css(".dictionary-wrap .cont"):
        term = _clean_text(" ".join(card.css(".subject a::text").getall()))
        definition = _clean_text(" ".join(card.css(".info2 ::text").getall()))
        if term and definition:
            rows.append(
                RawTerm(
                    term=term,
                    raw_definition=definition,
                    source_name=source_name,
                    source_url=source_url,
                    collected_at=collected_at,
                )
            )

    dts = page.css("dt")
    dds = page.css("dd")
    for dt, dd in zip(dts, dds, strict=False):
        term = _clean_text(" ".join(dt.css("::text").getall()))
        definition = _clean_text(" ".join(dd.css("::text").getall()))
        if term and definition:
            rows.append(
                RawTerm(
                    term=term,
                    raw_definition=definition,
                    source_name=source_name,
                    source_url=source_url,
                    collected_at=collected_at,
                )
            )

    for tr in page.css("tr"):
        cells = [_clean_text(text) for text in tr.css("td::text").getall()]
        if len(cells) >= 2 and cells[0] and cells[1]:
            rows.append(
                RawTerm(
                    term=cells[0],
                    raw_definition=cells[1],
                    source_name=source_name,
                    source_url=source_url,
                    collected_at=collected_at,
                )
            )
    return _dedupe_rows(rows)


def scrape_reference(
    source_name: str,
    source_url: str,
    fetch: Callable[[str], str] | None = None,
    max_pages: int = 15,
    dynamic_scrapers: dict[str, DynamicScraper] | None = None,
) -> tuple[list[RawTerm], list[ScrapeFailure]]:
    dynamic_scraper = _match_dynamic_scraper(source_url, dynamic_scrapers)
    if dynamic_scraper:
        try:
            return _dedupe_rows(dynamic_scraper(source_name, source_url)), []
        except Exception as exc:
            return [], [
                ScrapeFailure(
                    source_name=source_name,
                    source_url=source_url,
                    failure_stage="dynamic_fetch",
                    error_message=str(exc),
                    attempted_at=_now_iso(),
                )
            ]

    fetch = fetch or _fetch_html
    if "fsc.go.kr/in090301" in source_url:
        return _scrape_fsc_reference(source_name, source_url, fetch, max_pages)
    try:
        html = fetch(source_url)
    except Exception as exc:
        return [], [
            ScrapeFailure(
                source_name=source_name,
                source_url=source_url,
                failure_stage="fetch",
                error_message=str(exc),
                attempted_at=_now_iso(),
            )
        ]
    try:
        return extract_terms_from_html(html, source_name, source_url), []
    except Exception as exc:
        return [], [
            ScrapeFailure(
                source_name=source_name,
                source_url=source_url,
                failure_stage="parse",
                error_message=str(exc),
                attempted_at=_now_iso(),
            )
        ]


def _fetch_html(url: str) -> str:
    page = Fetcher.get(url, stealthy_headers=True, timeout=30)
    encoding = getattr(page, "encoding", None) or "utf-8"
    return page.body.decode(encoding, errors="replace")


def _match_dynamic_scraper(source_url: str, dynamic_scrapers: dict[str, DynamicScraper] | None = None) -> DynamicScraper | None:
    scrapers = dynamic_scrapers or _DYNAMIC_SCRAPERS
    for marker, scraper in scrapers.items():
        if marker in source_url:
            return scraper
    return None


def _fetch_dynamic(source_url: str, action: Callable[[Any], None]) -> None:
    DynamicFetcher.fetch(
        source_url,
        headless=True,
        network_idle=False,
        timeout=120_000,
        wait=500,
        page_action=action,
    )


def scrape_kb_reference(source_name: str, source_url: str) -> list[RawTerm]:
    collected_at = _now_iso()
    rows: list[RawTerm] = []

    def collect(page: Any) -> None:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2_000)
        frame = next((item for item in page.frames if item.name == "bbsIframe"), None)
        if frame is None:
            raise RuntimeError("KB dictionary iframe not found")

        for label in KB_THEME_LABELS:
            clicked = frame.evaluate(
                """(label) => {
                    const button = Array.from(document.querySelectorAll('.theme button'))
                        .find((item) => item.innerText.trim() === label);
                    if (!button) return false;
                    button.click();
                    return true;
                }""",
                label,
            )
            if not clicked:
                continue
            page.wait_for_timeout(700)
            items = frame.evaluate(
                """() => Array.from(document.querySelectorAll('.result-list li')).map((item) => {
                    const onclick = item.getAttribute('onclick') || '';
                    const match = onclick.match(/searchMeaning\\('([^']+)'\\)/);
                    return { id: match ? match[1] : '', term: item.innerText.trim() };
                }).filter((item) => item.id && item.term)"""
            )
            for item in items:
                frame.evaluate("(id) => searchMeaning(id)", item["id"])
                page.wait_for_timeout(80)
                detail_text = frame.evaluate("() => document.querySelector('.result-detail')?.innerText || ''")
                detail_term, definition = _split_title_definition(detail_text)
                row = _raw_term(detail_term or item["term"], definition, source_name, source_url, collected_at)
                if row:
                    rows.append(row)

    _fetch_dynamic(source_url, collect)
    return _dedupe_rows(rows)


def scrape_mirae_reference(source_name: str, source_url: str) -> list[RawTerm]:
    collected_at = _now_iso()
    rows: list[RawTerm] = []
    list_html = _fetch_html(source_url)
    for item in _extract_mirae_items(list_html):
        detail_html = _fetch_mirae_detail_html(source_url, item["id"])
        detail_text = "\n".join(Selector(detail_html).css(".result-inboxtxt ::text").getall())
        detail_term, definition = _split_title_definition(detail_text)
        row = _raw_term(detail_term or item["term"], definition, source_name, source_url, collected_at)
        if row:
            rows.append(row)
    return _dedupe_rows(rows)


def scrape_im_reference(source_name: str, source_url: str) -> list[RawTerm]:
    collected_at = _now_iso()
    rows: list[RawTerm] = []

    def collect(page: Any) -> None:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1_500)
        terms = page.evaluate(
            """() => (window.initObj || []).map((item) => ({
                title: item.title || '',
                body: item.body || '',
            }))"""
        )
        if not terms:
            raise RuntimeError("iM dictionary data object not found")
        for item in terms:
            row = _raw_term(item["title"], _clean_html_fragment(item["body"]), source_name, source_url, collected_at)
            if row:
                rows.append(row)

    _fetch_dynamic(source_url, collect)
    return _dedupe_rows(rows)


def _extract_mirae_items(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"""href=["']javascript:doView\('([^']+)'\);["'][^>]*>(.*?)</a>""", re.DOTALL)
    for item_id, raw_term in pattern.findall(html):
        term = _clean_html_fragment(raw_term)
        if item_id and term and item_id not in seen:
            seen.add(item_id)
            items.append({"id": item_id, "term": term})
    return items


def _fetch_mirae_detail_html(source_url: str, seq: str) -> str:
    page = Fetcher.post(
        f"{source_url}#seq_{seq}",
        data=f"searchStart=&searchEnd=&seq={seq}&searchValue=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        stealthy_headers=True,
        timeout=30,
    )
    encoding = getattr(page, "encoding", None) or "utf-8"
    return page.body.decode(encoding, errors="replace")


def _scrape_fsc_reference(
    source_name: str,
    source_url: str,
    fetch: Callable[[str], str],
    max_pages: int,
) -> tuple[list[RawTerm], list[ScrapeFailure]]:
    rows: list[RawTerm] = []
    failures: list[ScrapeFailure] = []
    for page_number in range(1, max_pages + 1):
        page_url = _with_query(source_url, {"curPage": str(page_number)})
        try:
            html = fetch(page_url)
            page_rows = extract_terms_from_html(html, source_name, source_url)
            if not page_rows:
                break
            rows.extend(page_rows)
        except Exception as exc:
            failures.append(
                ScrapeFailure(
                    source_name=source_name,
                    source_url=page_url,
                    failure_stage="fetch",
                    error_message=str(exc),
                    attempted_at=_now_iso(),
                )
            )
    return _dedupe_rows(rows), failures


def _with_query(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _dedupe_rows(rows: list[RawTerm]) -> list[RawTerm]:
    seen: set[tuple[str, str]] = set()
    deduped: list[RawTerm] = []
    for row in rows:
        key = (row.term, row.raw_definition)
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


_DYNAMIC_SCRAPERS: dict[str, DynamicScraper] = {
    "kbsec.com/go.able?linkcd=m04110000": scrape_kb_reference,
    "securities.miraeasset.com/hki/hki3028/r01.do": scrape_mirae_reference,
    "imfnsec.com/research/financial_guide/fg000000.jsp": scrape_im_reference,
}
