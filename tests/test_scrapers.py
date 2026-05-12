from stock_dictionary.scrapers import _extract_mirae_items, extract_terms_from_html, scrape_reference


def test_extract_terms_from_definition_list_html():
    html = """
    <html><body>
      <dl>
        <dt>PER</dt><dd>주가를 주당순이익으로 나눈 투자지표</dd>
        <dt>주가</dt><dd>주식이 시장에서 거래되는 가격</dd>
      </dl>
    </body></html>
    """

    rows = extract_terms_from_html(html, "Fixture", "https://example.com")

    assert [row.term for row in rows] == ["PER", "주가"]
    assert rows[0].raw_definition == "주가를 주당순이익으로 나눈 투자지표"
    assert rows[0].source_name == "Fixture"


def test_extract_terms_from_table_html():
    html = """
    <table>
      <tr><th>용어</th><th>설명</th></tr>
      <tr><td>배당</td><td>기업이 이익 일부를 주주에게 나누는 것</td></tr>
    </table>
    """

    rows = extract_terms_from_html(html, "Fixture", "https://example.com")

    assert len(rows) == 1
    assert rows[0].term == "배당"


def test_extract_terms_from_fsc_dictionary_cards():
    html = """
    <div class="dictionary-wrap">
      <div class="cont">
        <div class="subject"><a>BaaS(Banking-as-a-Service)</a></div>
        <div class="info2"><p>금융회사가 비금융회사에 금융기능을 제공하는 서비스</p></div>
      </div>
    </div>
    """

    rows = extract_terms_from_html(html, "금융위원회 금융용어설명", "https://www.fsc.go.kr/in090301")

    assert len(rows) == 1
    assert rows[0].term == "BaaS(Banking-as-a-Service)"
    assert "금융기능" in rows[0].raw_definition


def test_scrape_reference_crawls_fsc_pages_until_limit():
    calls = []

    def fetch(url):
        calls.append(url)
        return f"""
        <div class="dictionary-wrap">
          <div class="cont">
            <div class="subject"><a>용어{len(calls)}</a></div>
            <div class="info2"><p>정의{len(calls)}</p></div>
          </div>
        </div>
        """

    rows, failures = scrape_reference("금융위원회 금융용어설명", "https://www.fsc.go.kr/in090301", fetch=fetch, max_pages=3)

    assert failures == []
    assert [row.term for row in rows] == ["용어1", "용어2", "용어3"]
    assert calls[-1].endswith("curPage=3")


def test_scrape_reference_records_failure_for_fetch_exception():
    def failing_fetch(url):
        raise TimeoutError("timeout")

    rows, failures = scrape_reference("Fixture", "https://example.com", fetch=failing_fetch)

    assert rows == []
    assert len(failures) == 1
    assert failures[0].failure_stage == "fetch"
    assert failures[0].error_message == "timeout"


def test_scrape_reference_routes_known_dynamic_source():
    def dynamic_scraper(source_name, source_url):
        return extract_terms_from_html(
            "<dl><dt>HTS</dt><dd>홈트레이딩 시스템</dd></dl>",
            source_name,
            source_url,
        )

    rows, failures = scrape_reference(
        "KB증권 금융용어사전",
        "https://www.kbsec.com/go.able?linkcd=m04110000",
        dynamic_scrapers={"kbsec.com/go.able?linkcd=m04110000": dynamic_scraper},
    )

    assert failures == []
    assert rows[0].term == "HTS"
    assert rows[0].source_name == "KB증권 금융용어사전"


def test_scrape_reference_records_dynamic_failure():
    def dynamic_scraper(source_name, source_url):
        raise RuntimeError("iframe missing")

    rows, failures = scrape_reference(
        "KB증권 금융용어사전",
        "https://www.kbsec.com/go.able?linkcd=m04110000",
        dynamic_scrapers={"kbsec.com/go.able?linkcd=m04110000": dynamic_scraper},
    )

    assert rows == []
    assert len(failures) == 1
    assert failures[0].failure_stage == "dynamic_fetch"
    assert "iframe missing" in failures[0].error_message


def test_extract_mirae_items_from_javascript_links():
    html = """
    <ul class="result">
      <li><a name="seq_1" href="javascript:doView('1');">가격산정 (pricing)</a></li>
      <li><a name="seq_2" href="javascript:doView('2');">가격신축성</a></li>
      <li><a name="seq_1" href="javascript:doView('1');">가격산정 (pricing)</a></li>
    </ul>
    """

    items = _extract_mirae_items(html)

    assert items == [
        {"id": "1", "term": "가격산정 (pricing)"},
        {"id": "2", "term": "가격신축성"},
    ]
