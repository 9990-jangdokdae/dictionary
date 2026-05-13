역할: 주식 입문자가 뉴스·리포트·주가 화면에서 자주 만나는 누락 용어를 보강한다.

입력:
- seed_terms: 반드시 포함해야 하는 보강 후보다.
- existing_samples: 이미 사전에 있는 대표 용어 샘플이다. 같은 개념은 다시 만들지 않는다.
- target_categories: 자유 확장 후보를 제안할 수 있는 카테고리다.
- max_extra_terms_per_category: 카테고리별 자유 확장 상한이다.

작성 기준:
- seed_terms는 삭제하지 않는다. 표현이 어색하면 term, aliases, definition만 더 자연스럽게 다듬는다.
- 자유 확장 후보는 target_categories 안에서만 제안한다.
- 주식 뉴스 큐레이션 서비스에서 실제로 자주 보이는 용어만 추가한다.
- 일반 금융 상식이나 지나치게 전문적인 학술 용어는 제외한다.
- aliases에는 같은 개념의 약어, 영문명, 한글명만 넣는다.
- 띄어쓰기만 다른 표현은 aliases에 넣지 않는다.
- 투자 권유, 매수·매도 추천, 수익 보장 표현은 쓰지 않는다.
- 설명은 툴팁에서 바로 쓸 수 있게 국내주식 서비스 문맥으로 작성한다.

출력:
- JSON 객체 하나만 반환한다.
- JSON keys: terms
- terms는 객체 배열이다.
- 각 terms 항목의 keys: term, aliases, category, definition
- aliases는 배열이다. 값이 없으면 빈 배열을 사용한다.

좋은 출력 예:

```json
{
  "terms": [
    {
      "term": "YoY",
      "aliases": ["Year on Year", "전년 동기 대비"],
      "category": "리포트/실적 표현",
      "definition": "YoY는 전년 같은 기간과 비교한 증감률을 뜻합니다. 실적 기사에서는 계절 영향을 줄이고 성장 흐름을 비교할 때 자주 사용됩니다."
    }
  ]
}
```
