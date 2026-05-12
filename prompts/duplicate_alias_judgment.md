역할: 수집된 주식·금융 용어들이 같은 개념의 별칭인지, 별도 개념인지 판단한다.

입력:
- candidates: term, definition, category 목록

판단 기준:
- alias: 약어/전체 명칭, 한글명/영문명, 표기 차이처럼 같은 계산식·대상·사용 맥락을 가진 경우.
- separate: 개념 범위, 발생 조건, 계산 방식, 제도상 의미, 투자자 해석 포인트가 다른 경우.
- uncertain: 이름은 비슷하지만 근거가 약하거나, 뉴스·주식 서비스에서 서로 바꿔 쓸 때 사용자 이해가 달라질 수 있는 경우.
- 대표 용어는 국내주식 서비스에서 가장 흔한 표기를 우선한다. 약어가 더 널리 쓰이면 약어를 대표 용어로 둔다.
- 이름이 비슷하다는 이유만으로 alias로 판단하지 않는다.
- uncertain은 review_required_terms.csv 검토 대상으로 본다.

출력:
- Return only valid JSON.
- JSON 외의 텍스트, 마크다운 코드블록, 추가 key, null 금지.
- decision은 alias, separate, uncertain 중 하나다.
- JSON keys: decision, representative_term, aliases
- aliases는 배열이다. 값이 없으면 representative_term은 빈 문자열, aliases는 빈 배열을 사용한다.

Few-shot 예시 1
입력:
candidates:
- term: PER
  definition: 주가를 주당순이익으로 나눈 투자지표
  category: 투자지표/밸류에이션
- term: 주가수익비율
  definition: 주가를 주당순이익으로 나눈 비율
  category: 투자지표/밸류에이션
- term: P/E Ratio
  definition: price earning ratio
  category: 투자지표/밸류에이션

좋은 출력:
{"decision":"alias","representative_term":"PER","aliases":["주가수익비율","P/E Ratio"]}

Few-shot 예시 2
입력:
candidates:
- term: 유상증자
  definition: 회사가 투자자에게 대가를 받고 새 주식을 발행하는 것
  category: 공시/기업행위
- term: 무상증자
  definition: 주주에게 대가를 받지 않고 새 주식을 배정하는 것
  category: 공시/기업행위

좋은 출력:
{"decision":"separate","representative_term":"","aliases":[]}

Few-shot 예시 3
입력:
candidates:
- term: 베이시스
  definition: 선물과 현물의 가격 차이를 나타내는 값
  category: 가격/차트
- term: 괴리율
  definition: 기준 가격과 실제 가격의 차이를 비율로 나타낸 값
  category: 투자지표/밸류에이션

좋은 출력:
{"decision":"uncertain","representative_term":"","aliases":[]}
