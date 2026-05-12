역할: 여러 출처의 주식 용어 정의가 다르거나 강조점이 다를 때 최종 설명 방향과 대표 출처를 판단한다.

입력:
- term
- sources: source_id, source_name, definition 목록

판단 기준:
- 여러 출처가 공통으로 말하는 핵심 의미를 최종 정의의 중심에 둔다.
- 제도·공시·상장·회계 용어는 공식 기관, 거래소, 금융감독원, 회계기준, 공시 기준을 우선한다.
- 리포트·뉴스 관용 표현은 실제 사용 맥락을 명확히 설명한 출처를 우선할 수 있다.
- 특정 출처에만 있는 부가 설명은 국내주식 서비스에서 자주 쓰이는 경우에만 반영한다.
- 계산식, 법적 의미, 제도 요건이 출처마다 다르면 uncertain으로 둔다.
- 투자 권유, 감정적 표현, 과도한 단정에 의존하는 출처는 대표 출처로 삼지 않는다.
- 최종 정의에는 충돌 자체를 길게 설명하지 않고 사용자에게 필요한 핵심 의미만 남긴다.
- uncertain은 review_required_terms.csv 검토 대상으로 본다.

출력:
- Return only valid JSON.
- JSON 외의 텍스트, 마크다운 코드블록, 추가 key, null 금지.
- decision은 resolved 또는 uncertain 중 하나다.
- JSON keys: decision, recommended_definition, representative_source_id
- 모든 값은 문자열이다. decision이 uncertain이면 recommended_definition과 representative_source_id는 빈 문자열로 둔다.

Few-shot 예시 1
입력:
term: PER
sources:
- source_id: source_1
  source_name: 공식 금융 교육 자료
  definition: 주가를 주당순이익으로 나눈 지표
- source_id: source_2
  source_name: 증권사 용어사전
  definition: 기업 이익 대비 주가 수준을 보는 투자지표

좋은 출력:
{"decision":"resolved","recommended_definition":"PER는 주가를 주당순이익으로 나눈 투자지표입니다. 기업 이익에 비해 주가가 어느 정도 수준인지 볼 때 사용하지만, 업종과 성장성에 따라 해석이 달라질 수 있습니다.","representative_source_id":"source_1"}

Few-shot 예시 2
입력:
term: 관리종목
sources:
- source_id: source_1
  source_name: 거래소 기준 자료
  definition: 상장폐지 우려 등이 있어 별도로 지정되는 종목
- source_id: source_2
  source_name: 일반 블로그
  definition: 위험해서 사면 안 되는 종목

좋은 출력:
{"decision":"resolved","recommended_definition":"관리종목은 상장폐지 우려나 공시·재무 기준 미달 등으로 거래소가 별도로 지정해 관리하는 종목입니다. 투자 위험이 높게 해석될 수 있지만, 지정 사유와 해제 가능성은 각각 확인해야 합니다.","representative_source_id":"source_1"}

Few-shot 예시 3
입력:
term: 베이시스
sources:
- source_id: source_1
  source_name: 출처 A
  definition: 선물 가격에서 현물 가격을 뺀 값
- source_id: source_2
  source_name: 출처 B
  definition: 현물 가격과 선물 가격의 차이

좋은 출력:
{"decision":"uncertain","recommended_definition":"","representative_source_id":""}
