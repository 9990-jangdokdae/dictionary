# PRD: 국내주식 웹 서비스용 주식 용어 사전 구축

- 문서 버전: v0.1
- 작성일: 2026-05-12
- 대상 서비스: 국내주식 이슈 요약/모니터링 웹 서비스
- 대상 데이터베이스: PostgreSQL / Neon Cloud Database
- GitHub Repository: https://github.com/9990-jangdokdae/dictionary.git
- 문서 목적: 주식 초보자용 용어 사전 구축 범위, 작성 원칙, 수집 기준, 검수 기준, 데이터 요구사항을 정의한다.

---

## 1. 프로젝트 개요

본 프로젝트는 국내주식 웹 서비스에서 사용자가 뉴스, 주가 데이터, 재무제표, 기업보고서, 리포트성 설명을 읽는 과정에서 마주치는 주식·금융 용어를 쉽게 이해할 수 있도록 돕는 **주식 용어 사전 데이터베이스**를 구축하는 것을 목표로 한다.

만들어진 데이터베이스는 Neon 데이터베이스 관리자에게 전달하기에 적합한 구조로 만들어야한다.
따라서 우선 SQLite 기반으로 데이터베이스를 구축 및 검증을 진행하고, 이후 SQLite 데이터베이스 파일과 Neon에서 마이그레이션/업로드 방법 문서를 같이 제공하는 것으로 한다.

용어 사전은 웹 서비스 내 **툴팁** 형태로 우선 활용된다. 다만 툴팁이라고 해서 반드시 짧게 작성하지는 않는다. 설명이 길어지더라도 용어의 의미가 명확하게 전달되고, 주식 초보자가 이해할 수 있으며, 문장 가독성이 좋다면 허용한다.

### 1.1 최종 산출물

본 프로젝트의 1차 산출물은 다음 4개로 정의한다.

| 산출물 | 설명 |
|---|---|
| `stock_dictionary.sqlite` | 초기 구축 및 검증용 SQLite 데이터베이스 파일 |
| `schema.postgres.sql` | Neon/PostgreSQL에 적용 가능한 테이블 생성 SQL |
| `seed_terms.csv` | 초기 용어 데이터 반영용 기본 파일 |
| `seed_terms.sql` | 초기 용어 데이터 반영용 보조 SQL 파일 |
| `upload_to_neon.md` | Neon에 스키마와 seed 데이터를 업로드하는 절차 문서 |
| `migration_to_neon.md` | SQLite 검증 결과를 Neon/PostgreSQL 구조로 이관하는 절차 문서 |

`stock_dictionary.sqlite`, `schema.postgres.sql`, `seed_terms.csv`, `seed_terms.sql`은 코드로 생성할 수 있는 데이터 산출물이다.

`upload_to_neon.md`, `migration_to_neon.md`는 자동 생성 코드의 대상이 아니다. 두 문서는 프로젝트 담당자에게 전달할 절차 문서로, Codex가 최종 데이터 산출물과 검증 결과를 확인한 뒤 직접 작성한다. 파이프라인 코드, exporter, 테스트는 이 두 문서의 자동 생성을 기대하거나 구현하지 않는다.

작업 중간 산출물로는 `raw_terms.csv`와 `cleaned_terms.csv`를 생성할 수 있다. 중간 산출물은 수집 결과 검토, 중복 제거, 범위 필터링, 별칭 분리 과정을 확인하기 위한 용도로 사용한다.

자동 처리 중 사람 검수가 필요한 항목은 CSV 형식의 검수 로그 파일인 `review_required_terms.csv`에 기록한다.

---

## 2. 배경

주식 초보자는 `매수`, `매도`, `주가`, `매출`, `영업이익` 같은 기본 용어뿐 아니라 `베이시스`, `PER`, `PBR`, `컨센서스`, `YoY`, `QoQ` 같은 전문적 표현도 서비스 이용 중 접할 수 있다.

특히 이슈 요약형 주식 서비스에서는 뉴스, 주가 변동, 재무제표, 기업보고서, 증권 리포트성 표현이 함께 등장하기 때문에 일반적인 금융용어사전만으로는 서비스 문맥을 충분히 설명하기 어렵다.

따라서 본 프로젝트는 먼저 검증 가능한 기존 용어 사전 레퍼런스를 기반으로 기본 주식 용어 사전을 구축하고, 이후 재무제표·기업보고서·리포트·뉴스에서 자주 등장하는 용어를 LLM으로 보완·정제하는 단계적 방식을 따른다.

---

## 3. 목표

### 3.1 핵심 목표

- 국내주식 웹 서비스에서 사용할 수 있는 주식 용어 사전 DB를 구축한다.
- 주식 초보자가 이해할 수 있는 설명글 형식을 정의한다.
- 용어별 출처를 기록하여 검수 가능성을 확보한다.
- PostgreSQL 데이터베이스에 저장 가능한 구조로 설계한다.
- 향후 LLM을 활용한 용어 확장 작업이 가능하도록 데이터 구조를 설계한다.

### 3.2 비목표

- 투자 추천, 매수·매도 판단 제공은 하지 않는다.
- 해외주식 전용 용어 사전은 1차 범위에 포함하지 않는다.
- 펀드, 채권, ELS/DLS, CMA, RP, 발행어음 등 금융상품 전반을 포괄하는 사전은 1차 범위에 포함하지 않는다.
- 자동 업데이트 시스템이나 관리자 페이지 구축은 1차 범위에 포함하지 않는다.

---

## 4. 주요 사용자

| 항목 | 내용 |
|---|---|
| 주요 사용자 | 주식 입문자, 주식 초보자, 주린이 |
| 지식 수준 | 기본적인 주식 계좌 개설, 종목 검색, 매수·매도 개념은 접했지만 재무·공시·지표·리포트 용어에는 익숙하지 않은 수준 |
| 사용 목적 | 서비스 화면에서 모르는 용어를 즉시 이해 |
| 설명 선호 | 짧은 정의보다 명확하고 쉬운 설명 |

---

## 5. 사용처

| 사용처 | 설명 |
|---|---|
| 용어 툴팁 | 뉴스, 이슈 요약, 주가 데이터, 재무지표 화면에서 용어 설명 |
| 상세 설명 모달 | 툴팁보다 긴 설명이 필요한 경우 확장 제공 |
| 용어 사전 페이지 | 향후 전체 용어 검색 및 탐색용 페이지로 확장 가능 |
| LLM 응답 보조 데이터 | 향후 AI 요약/설명 기능에서 용어 정의 근거로 활용 가능 |

---

## 6. 서비스 범위

### 6.1 시장 범위

| 항목 | 포함 여부 |
|---|---|
| 국내주식 | 포함 |
| 코스피 | 포함 |
| 코스닥 | 포함 |
| 코넥스 | 후순위 또는 보류 |
| 미국주식 | 제외 |
| 해외주식 | 제외 |
| 국내 ETF/ETN | 서비스 노출 여부에 따라 제한 포함 가능 |
| 채권 | 제외 또는 후순위 |
| 펀드 | 제외 또는 후순위 |
| ELS/DLS | 제외 또는 후순위 |
| CMA/RP/발행어음 | 제외 |

### 6.2 언어 범위

| 항목 | 기준 |
|---|---|
| 기본 언어 | 한국어 |
| 대표 용어 | 한국어 우선 |
| 영어 약어 | 국내주식 서비스에서 자주 등장하면 포함 |
| 영문명 | 별칭 또는 보조 필드로 관리 |
| 한자어 | 필요한 경우 별칭 또는 설명 내 보조 표현으로 관리 |

---

## 7. 용어 구축 전략

본 프로젝트는 두 단계로 용어를 구축한다.

### 7.1 1단계: 기존 용어 사전 레퍼런스 기반 구축

먼저 검증 가능한 기존 용어 사전 레퍼런스를 기반으로 기본적인 주식·금융 용어를 수집한다.

이 단계의 목적은 다음과 같다.

- 기본 주식 용어 확보
- 설명글 형식 표준화
- 출처 기록 방식 검증
- DB 저장 구조 검증
- 수집 후 중복 제거와 전처리를 거친 유효 용어 수 확인

예상 용어군:

| 영역 | 예시 |
|---|---|
| 기초 주식 용어 | 주식, 주가, 종목, 매수, 매도 |
| 시장/상장 용어 | 코스피, 코스닥, IPO, 상장, 관리종목 |
| 가격/차트 용어 | 시가, 고가, 저가, 종가, 이동평균선, 갭 |
| 거래/주문/결제 용어 | 주문, 체결, 호가, 공매도, 신용거래, 결제 |
| 공시/기업행위 용어 | 공시, 유상증자, 무상증자, 감자, 합병, 분할 |
| 재무/회계 용어 | 매출, 영업이익, 당기순이익, 자산, 부채, 자본 |
| 투자지표/밸류에이션 | PER, PBR, ROE, EPS, BPS, EV/EBITDA |
| 수급/투자자 용어 | 개인, 기관, 외국인, 순매수, 순매도 |
| 상품/시장 보조 용어 | ETF, ETN, ELS, DLS, 채권, 금리, 환율 |

### 7.2 2단계: LLM 기반 보완 및 정제

기존 용어 사전 레퍼런스에서 충분히 찾기 어려운 용어는 이후 LLM을 활용해 정의를 보완한다. LLM은 용어 정의 작성뿐 아니라 전처리, 중복 판단, 별칭 후보 판단, 카테고리 후보 판단, 출처 간 정의 충돌 해석에도 활용할 수 있다.

이 단계의 대상은 다음과 같다.

| 영역 | 예시 |
|---|---|
| 실적 비교 약어 | YoY, QoQ, MoM, YTD, TTM |
| 리포트 표현 | 컨센서스, 목표주가, 투자의견, 커버리지 |
| 실적 시즌 용어 | 어닝 서프라이즈, 어닝 쇼크, 가이던스 |
| 뉴스 관용어 | 수급, 모멘텀, 투자심리, 차익실현 |
| 기업보고서 용어 | 연결재무제표, 별도재무제표, 감사의견 |
| 공시 이벤트 용어 | 전환사채, 신주인수권부사채, 자기주식 취득 |
| 주가 해석 표현 | 급등, 급락, 반등, 조정, 박스권 |

LLM은 단순 초안 생성 도구가 아니라 고품질 용어 데이터베이스 구축을 위한 **데이터 정제 및 판단 보조 도구**로 사용한다.

LLM을 활용할 수 있는 작업은 다음과 같다.

| 활용 영역 | 설명 |
|---|---|
| 미흡한 용어 정의 보완 | 기존 레퍼런스 설명이 너무 어렵거나 서비스 문맥에 부족한 경우 초보자 친화적으로 재작성 |
| 중복 판단 | 같은 개념의 용어인지, 별도 용어로 분리해야 하는지 판단 |
| 별칭 후보 판단 | 약어, 영문명, 띄어쓰기 차이, 한글 표현 차이가 별칭으로 적절한지 판단 |
| 카테고리 후보 판단 | 초기 카테고리 중 어느 분류가 적절한지 판단 |
| 출처 충돌 해석 | 여러 출처의 정의가 다를 때 국내주식 서비스 문맥에서 어떤 정의가 적절한지 판단 |
| 설명 품질 개선 | 투자 조언으로 오해될 표현 제거, 문장 가독성 개선, 초보자 친화성 강화 |

다만 LLM이 생성하거나 판단한 결과는 가능한 한 원 출처 URL과 함께 검토되어야 하며, 최종 서비스 반영 전 사람 검수를 거친다.

### 7.3 초기 용어 개수 기준

초기 용어 개수는 사전에 고정하지 않는다.

1~3차 레퍼런스에서 용어 후보를 수집한 뒤, 중복 용어 정리, 대표 용어와 별칭 분리, 범위 필터링을 포함한 전처리를 진행한다.

전처리 후 유효 용어 수가 **100개 이하가 아니라면** 구축을 계속 진행한다. 전처리 후 유효 용어 수가 **100개 이하인 경우** 레퍼런스 범위, 수집 방식, 포함 기준을 재검토한다.

---

## 8. 레퍼런스 목록

아래 레퍼런스는 현재 단계에서 활용 대상으로 지정한다.  
기획재정부 시사경제용어사전은 3차 후보에서 제외한다.

### 8.1 1차 레퍼런스

| 우선순위 | 레퍼런스 | 정확한 URL | 활용 목적 |
|---:|---|---|---|
| 1 | KB증권 금융용어사전 | https://www.kbsec.com/go.able?linkcd=m04110000 | 메인 기준 레퍼런스. 기초~전문 용어가 함께 있는 사전 구조와 설명 톤 참고 |
| 2 | 금융위원회 금융용어설명 | https://www.fsc.go.kr/in090301 | 공식 금융 용어 확인 및 출처 기록용 |

### 8.2 2차 레퍼런스

| 우선순위 | 레퍼런스 | 정확한 URL | 활용 목적 |
|---:|---|---|---|
| 3 | 미래에셋증권 증권용어사전 | https://securities.miraeasset.com/hki/hki3028/r01.do | 증권 용어 후보 보완 |
| 4 | iM증권 금융용어사전 | https://www.imfnsec.com/research/financial_guide/fg000000.jsp | 금융·투자 용어 후보 보완 |
| 5 | 한국투자증권 경제용어사전 | https://www.truefriend.com/main/research/dic/Dic.jsp | 경제·시장·증권 관련 용어 보완 |

### 8.3 3차 레퍼런스

| 우선순위 | 레퍼런스 | 정확한 URL | 활용 목적 |
|---:|---|---|---|
| 6 | KDI 경제교육·정보센터 시사용어사전 | https://eiec.kdi.re.kr/material/wordDic.do | 경제·금융·경영 용어 보조 확인 |
| 7 | 신한투자증권 주식 용어 가이드 | https://www.shinhansec.com/siw/insights/guide/stock_term_guide/contents.do | 주식 초보자용 설명 흐름 및 표현 톤 참고 |

---

## 9. 용어 포함 기준

### 9.1 우선 포함

| 기준 | 설명 |
|---|---|
| 국내주식 서비스 화면에서 노출 가능성이 높은 용어 | 예: 주가, 거래량, 시가총액, 매출, 영업이익 |
| 주식 초보자가 이해하기 어려운 용어 | 예: 호가, 체결, 권리락, 베이시스 |
| 뉴스·이슈 요약에서 자주 등장하는 용어 | 예: 공시, 증자, 감자, 배당, 수급 |
| 재무제표 이해에 필요한 용어 | 예: 매출액, 영업이익, 당기순이익, 자산, 부채 |
| 투자지표 해석에 필요한 용어 | 예: PER, PBR, ROE, EPS, BPS |
| 국내주식 시장 구조와 관련된 용어 | 예: 코스피, 코스닥, 상장, 관리종목 |

### 9.2 조건부 포함

| 영역 | 기준 |
|---|---|
| ETF/ETN | 주식 서비스 화면에서 실제로 노출되는 경우 포함 |
| 신용/대출 | 신용거래, 미수거래, 증거금 등 주식 거래와 직접 관련된 경우 포함 |
| 파생상품 | 베이시스 등 주식시장 해석에 필요한 일부 용어만 포함 |
| 거시경제 용어 | 금리, 환율, 물가 등 주가 이슈 설명에 자주 필요한 경우 포함 |

### 9.3 제외 또는 후순위

| 영역 | 이유 |
|---|---|
| 채권 일반 | 국내주식 서비스 핵심 범위 밖 |
| 펀드 일반 | 직접 주식 서비스 범위와 거리 있음 |
| ELS/DLS | 금융상품 영역이 강함 |
| CMA/RP/발행어음 | 현재 서비스 목적과 거리 있음 |
| 보험·대출·부동산 | 주식 용어 사전 범위 밖 |
| 해외주식 전용 제도 | 1차 범위 밖 |

---

## 10. 설명글 작성 원칙

### 10.1 핵심 원칙

> 설명은 짧은 것보다 명확한 것이 우선이다.  
> 다만 길어지더라도 문장은 짧게 나누고, 주식 초보자가 이해할 수 있는 표현을 사용한다.

### 10.2 설명 구조

각 용어 설명은 가능하면 다음 흐름을 따른다.

1. 용어의 뜻을 먼저 쉽게 설명한다.
2. 주식 서비스나 뉴스에서 어떤 맥락으로 쓰이는지 설명한다.
3. 초보자가 오해하기 쉬운 점을 덧붙인다.
4. 필요한 경우 간단한 예시를 포함한다.

### 10.3 권장 설명 예시

#### 매출

> 매출은 기업이 상품이나 서비스를 팔아 벌어들인 총금액입니다. 아직 비용을 빼기 전의 금액이기 때문에, 매출이 늘었다고 해서 반드시 이익이 늘었다는 뜻은 아닙니다. 주식 뉴스에서는 기업의 성장 규모를 볼 때 자주 사용됩니다.

#### 베이시스

> 베이시스는 선물 가격과 현물 가격의 차이를 뜻합니다. 보통 선물 가격에서 현물 가격을 뺀 값으로 계산합니다. 주식 초보자에게는 다소 어려운 용어지만, 선물시장과 현물시장의 가격 차이를 볼 때 쓰이는 표현이라고 이해하면 됩니다.

#### YoY

> YoY는 전년 같은 기간과 비교한다는 뜻입니다. 예를 들어 2026년 2분기 매출을 2025년 2분기 매출과 비교할 때 사용합니다. 계절 영향을 줄이고 실적이 실제로 좋아졌는지 볼 때 자주 쓰입니다.

---

## 11. 금지 표현 및 주의사항

### 11.1 금지 표현

용어 설명은 투자 조언으로 오해될 수 있는 표현을 피한다.

| 금지 표현 | 이유 |
|---|---|
| 이 지표가 높으면 좋은 주식입니다 | 단정적 투자 판단 |
| 이 경우 매수하는 것이 좋습니다 | 매수 권유 |
| 반드시 주가가 상승합니다 | 수익 보장 오해 |
| 안전한 투자입니다 | 위험 축소 표현 |
| 이 종목은 저평가입니다 | 개별 종목 판단 |

### 11.2 권장 표현

| 권장 표현 | 이유 |
|---|---|
| 일반적으로 긍정적으로 해석될 수 있습니다 | 단정 회피 |
| 다만 다른 지표와 함께 보는 것이 좋습니다 | 균형 제공 |
| 상황에 따라 다르게 해석될 수 있습니다 | 맥락 강조 |
| 투자 판단에는 추가 정보가 필요합니다 | 투자 조언 회피 |

---

## 12. 데이터 요구사항

용어 데이터는 PostgreSQL에 저장될 예정이며, 향후 Neon Cloud Database로 구축 후 전달한다.

1차 구축에서는 툴팁 활용을 우선하므로 단일 테이블 중심의 가벼운 구조를 사용한다.

### 12.1 단일 테이블 필수 컬럼

| 필드 | 설명 |
|---|---|
| `id` | 고유 ID |
| `term` | 대표 용어명 |
| `aliases` | 별칭, 약어, 영문명 목록 |
| `category` | 카테고리 |
| `definition` | 주린이 친화적 설명 |
| `source_name` | 용어 수집 출처명 |
| `source_url` | 용어 수집 출처 URL |
| `created_at` | 생성일 |
| `updated_at` | 수정일 |

### 12.2 `aliases` 저장 방식

`aliases`는 List 기반 JSON 배열로 저장한다.

예:

```json
["주가수익비율", "Price Earnings Ratio", "P/E Ratio"]
```

SQLite에서는 `TEXT` 컬럼에 JSON 배열 문자열로 저장하고 `json_valid(aliases)` 제약으로 유효성을 검증한다. Neon/PostgreSQL에서는 `JSONB` 컬럼으로 이관한다.

별칭이 없는 용어의 `aliases`는 빈 문자열이나 `NULL`이 아니라 항상 빈 JSON 배열 문자열 `[]`로 저장한다.

수집된 `term` 안에 괄호로 포함된 한글명, 영문명, 약어는 대표 용어와 분리하여 `aliases`에 저장한다. 예를 들어 `ELS(주가연계증권)`은 대표 용어를 `ELS`로 두고 `주가연계증권`을 `aliases`에 저장한다.

띄어쓰기만 다른 표현은 `aliases`에 저장하지 않고 검색 또는 매칭 단계의 정규화 대상으로 본다.

### 12.3 출처 저장 방식

최종 DB에는 대표 출처 1개만 저장한다.

여러 출처를 참고한 경우에도 최종 DB의 `source_name`, `source_url`에는 최종 설명 작성에 가장 기준이 된 대표 출처 1개만 기록한다. 복수 출처 목록, 출처 간 비교 메모, LLM 판단 메모는 필요한 경우 중간 산출물 또는 별도 작업 로그에서만 관리한다.

대표 출처는 다음 우선순위를 기준으로 선택한다.

1. 공식 기관 출처
2. 1차 기준 레퍼런스
3. 증권사 용어사전
4. 보조 레퍼런스

### 12.4 SQLite 기준 테이블 구조

```sql
CREATE TABLE stock_terms (
  id INTEGER PRIMARY KEY,
  term TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases)),
  category TEXT NOT NULL,
  definition TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 12.5 PostgreSQL/Neon 기준 테이블 구조

```sql
CREATE TABLE stock_terms (
  id BIGSERIAL PRIMARY KEY,
  term TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  category TEXT NOT NULL,
  definition TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 13. 구축 프로세스

### 13.1 1차 구축 프로세스

1. Scrapling 기반 수집 파이프라인 구축
2. 1~3차 레퍼런스에서 용어 후보 수집
3. 수집 원본을 `raw_terms.csv`로 저장
4. 전처리 및 LLM 보조 정제 파이프라인 실행
5. 국내주식 서비스 범위에 맞는 용어만 필터링
6. 중복 용어 정리
7. 대표 용어와 별칭 분리
8. 카테고리 부여
9. 설명글 형식 통일
10. 출처 URL 기록
11. 전처리 및 LLM 보조 정제 결과를 `cleaned_terms.csv`로 저장
12. 전처리 후 유효 용어 수 확인
13. 사람 검수 대상 로그 확인
14. SQLite DB 구축 및 검증
15. PostgreSQL/Neon용 schema, seed, upload, migration 문서 생성

### 13.2 LLM 보완 및 정제 프로세스

1. 뉴스, 재무제표, 기업보고서, 리포트성 콘텐츠에서 용어 후보 추출
2. 기존 용어 사전에 없는 용어 식별
3. 기존 레퍼런스 설명이 미흡한 용어 식별
4. 중복 용어, 별칭 후보, 카테고리 후보를 LLM으로 보조 판단
5. 출처 간 정의 충돌이 있는 경우 LLM으로 국내주식 서비스 문맥에 적절한 정의 후보를 도출
6. LLM으로 설명을 서비스 스타일 가이드에 맞게 정규화
7. 출처 또는 추출 근거 기록
8. 사람 검수 대상 로그 확인
9. SQLite DB 및 Neon 이관 파일에 반영

### 13.3 데이터 수집 파이프라인

데이터 수집은 Scrapling 기반 파이프라인으로 구축한다.

수집 파이프라인은 레퍼런스 사이트별 수집기를 두고, 각 수집기의 결과를 공통 중간 형식으로 변환한다.

기본 흐름은 다음과 같다.

```text
레퍼런스 사이트
→ Scrapling 수집기
→ raw_terms.csv
→ 전처리 및 LLM 보조 정제 파이프라인
→ cleaned_terms.csv
→ stock_dictionary.sqlite
→ schema.postgres.sql / seed_terms.csv / seed_terms.sql / upload_to_neon.md / migration_to_neon.md
```

`raw_terms.csv`는 가능한 한 원 출처의 값을 보존한다. `cleaned_terms.csv`는 최종 DB 컬럼 구조에 맞춘 정제 결과로 사용한다.

LLM 개입 여부, LLM 판단 메모, 검수 메모 등 작업 과정의 추적 정보는 최종 DB 컬럼에 포함하지 않는다. 필요한 경우 중간 산출물 또는 별도 CSV 로그에서만 관리한다.

사람 검수가 필요한 항목은 `review_required_terms.csv`에 기록한다. 사람 검수는 파이프라인 내부의 Human-in-the-loop 기능으로 구현하지 않고, 프로젝트 담당자가 별도로 수동 진행한다.

대상은 다음과 같다.

- LLM JSON 파싱 또는 Pydantic 검증에 3차 실패한 항목
- 중복/별칭 판단 결과가 `uncertain`인 항목
- 출처 충돌 판단 결과가 `uncertain`인 항목
- 카테고리 판단이 불명확한 항목
- 출처 충돌이 커서 자동 반영이 부적절한 항목

`review_required_terms.csv`의 기본 컬럼은 다음과 같다.

```text
term
aliases
category
reason
source_name
source_url
notes
```

### 13.4 LLM 샘플 검증 산출물

LLM 파이프라인은 비용과 품질을 검증하기 위해 `data/llm_samples/` 아래에 단계별 샘플 산출물을 만들 수 있다.

샘플 산출물은 최종 DB 입력 파일이 아니라, 각 LLM 단계의 실행 결과와 검수 대상을 확인하기 위한 중간 파일이다. 파일별 행 수는 단계의 성격에 따라 다를 수 있으며, 모든 파일이 동일한 용어 수를 가져야 하는 것은 아니다.

| 파일 | 의미 | 행 수 기준 |
|---|---|---|
| `category_assignment_all.csv` | 카테고리 분류를 실행한 전체 샘플 결과 | 입력 샘플 수와 같다. |
| `category_assignment_results.csv` | `category_gate`를 통과해 다음 단계로 넘어갈 카테고리 결과 | `category_assignment_all.csv`에서 `기타`를 제외한 수다. |
| `category_assignment_excluded.csv` | `기타`로 분류되어 다음 LLM 단계에서 제외된 항목 | 제외 항목 수만큼 기록한다. |
| `category_assignment_review.csv` | 카테고리 분류 중 JSON 파싱, Pydantic 검증, 실행 실패가 발생한 항목 | 문제가 없으면 header만 있는 빈 CSV가 정상이다. |
| `duplicate_alias_judgment_results.csv` | 중복/별칭 후보 그룹에 대해서만 LLM이 판단한 결과 | 전체 입력 수가 아니라 후보 그룹 수와 같다. |
| `duplicate_alias_judgment_review.csv` | 중복/별칭 판단 실패 또는 `uncertain` 항목 | 문제가 없으면 header만 있는 빈 CSV가 정상이다. |
| `definition_rewrite_results.csv` | 설명 정제를 실행한 결과 | 해당 단계 입력 수와 같다. |
| `definition_rewrite_review.csv` | 설명 정제 실패 또는 `uncertain` 항목 | 문제가 없으면 header만 있는 빈 CSV가 정상이다. |
| `source_conflict_resolution_results.csv` | 복수 출처 정의가 있어 충돌 판단이 필요한 후보만 처리한 결과 | 전체 입력 수가 아니라 충돌 후보 그룹 수와 같다. |
| `source_conflict_resolution_review.csv` | 출처 충돌 판단 실패 또는 `uncertain` 항목 | 문제가 없으면 header만 있는 빈 CSV가 정상이다. |

`duplicate_alias_judgment_results.csv`와 `source_conflict_resolution_results.csv`는 1개 용어마다 반드시 1행을 생성하지 않는다. 두 파일은 후보가 있는 경우에만 행이 생기는 보조 판단 결과다.

`*_review.csv` 파일은 오류나 `uncertain`이 없을 때 header만 존재할 수 있다. 이는 빈 결과가 아니라 해당 단계에서 사람 검수 대상이 없었다는 의미다.

Scrapling CLI를 사용할 경우 프롬프트 인젝션 방지를 위해 `--ai-targeted` 옵션을 사용한다. Python 코드로 수집기를 작성하는 경우에는 대상 사이트의 robots.txt와 이용 조건을 확인하고, 과도한 요청을 피하기 위해 필요한 경우 요청 지연을 둔다.

보호된 페이지, 로그인 영역, 유료 콘텐츠, 개인정보성 데이터는 수집 대상에서 제외한다.

### 13.5 파일 및 디렉터리 구조

파이프라인은 다음 파일 및 디렉터리 구조를 기준으로 구성한다.

```text
scripts/
  scrape_terms.py
  preprocess_terms.py
  build_sqlite.py
  export_postgres.py

data/
  raw_terms.csv
  cleaned_terms.csv
  review_required_terms.csv
  scrape_failures.csv

output/
  stock_dictionary.sqlite
  schema.postgres.sql
  seed_terms.csv
  seed_terms.sql
```

`scripts/`는 수집, 전처리 및 LLM 보조 정제, SQLite 생성, PostgreSQL/Neon 데이터 산출물 생성을 담당한다. `data/`는 사람이 확인할 중간 CSV와 검수 로그를 보관한다. `output/`은 코드로 생성되는 데이터 산출물을 보관한다.

`upload_to_neon.md`, `migration_to_neon.md`는 위 코드 생성 파일 구조에 포함하지 않는다. 두 문서는 최종 데이터 산출물 생성 후 Codex가 직접 작성하여 전달한다.

### 13.6 중간 CSV 컬럼 구조

`raw_terms.csv`는 수집 원본을 가능한 한 보존하기 위한 중간 파일이다.

| 컬럼 | 설명 |
|---|---|
| `term` | 수집된 용어명 |
| `raw_definition` | 원 출처에서 수집한 설명 또는 정의 |
| `source_name` | 수집 출처명 |
| `source_url` | 수집 출처 URL |
| `collected_at` | 수집 시각 |

`cleaned_terms.csv`는 최종 DB에 적재할 수 있는 형태로 정제된 파일이다.

| 컬럼 | 설명 |
|---|---|
| `term` | 대표 용어명 |
| `aliases` | JSON 배열 문자열 형태의 별칭 목록 |
| `category` | 초기 카테고리 |
| `definition` | 서비스용 설명 |
| `source_name` | 대표 출처명 |
| `source_url` | 대표 출처 URL |

### 13.7 대표 용어 선정 기준

중복 제거와 별칭 분리 과정에서 대표 용어는 다음 우선순위로 선정한다.

1. 국내주식 서비스에서 가장 자주 보일 표현을 우선한다.
2. 한국어 용어를 우선한다.
3. 단, `PER`, `PBR`, `ROE`, `EPS`, `BPS`, `YoY`, `QoQ`처럼 약어 자체가 더 일반적인 경우 약어를 대표 용어로 사용한다.
4. 띄어쓰기 변형이 있으면 붙여 쓰는 표기를 우선한다.
5. 출처 우선순위가 높은 곳에서 사용하는 표기를 참고한다.

예:

| 후보 | 대표 용어 | aliases |
|---|---|---|
| `PER`, `주가수익비율`, `P/E Ratio` | `PER` | `["주가수익비율", "P/E Ratio"]` |
| `유상 증자`, `유상증자` | `유상증자` | `["유상 증자"]` |
| `전년 동기 대비`, `YoY`, `Year on Year` | `YoY` | `["전년 동기 대비", "Year on Year"]` |

### 13.8 수집 실패 처리 기준

수집 파이프라인 작성 단계에서는 각 레퍼런스 수집기가 실패하지 않을 때까지 검증한다.

실제 수집 실행 단계에서 특정 레퍼런스 수집이 실패하는 경우에는 전체 파이프라인을 즉시 중단하지 않고 간단한 실패 로그를 남긴다. 실패 로그는 수집 종료 후 확인하고 필요 시 수동 또는 반수동 방식으로 보완한다.

수집 실패 로그는 `scrape_failures.csv`로 관리한다.

기본 컬럼은 다음과 같다.

```text
source_name
source_url
failure_stage
error_message
attempted_at
```

---

## 14. 검수 기준

| 검수 항목 | 기준 |
|---|---|
| 출처 확인 | 모든 용어는 최소 1개 이상의 출처 URL을 가져야 함 |
| 설명 정확성 | 용어의 의미가 금융·주식 맥락에서 틀리지 않아야 함 |
| 초보자 친화성 | 전문 용어를 다시 전문 용어로 설명하지 않아야 함 |
| 투자 조언 회피 | 매수·매도 권유로 해석될 문장이 없어야 함 |
| 가독성 | 긴 설명도 짧은 문장으로 나누어야 함 |
| 중복 관리 | 같은 개념의 용어는 대표 용어와 별칭으로 분리해야 함 |
| 범위 적합성 | 국내주식 서비스와 관련성이 낮은 금융상품 용어는 제외 또는 보류해야 함 |
| LLM 활용 결과 검토 | LLM이 보완·판단한 용어는 원 출처 또는 추출 근거와 함께 검토해야 함 |

### 14.1 출처 충돌 처리 기준

여러 출처의 정의가 서로 다르거나 설명 범위가 충돌하는 경우 다음 기준으로 처리한다.

1. 공식 기관 출처를 우선 검토한다.
2. 국내주식 서비스 문맥에 더 직접적으로 맞는 정의를 우선한다.
3. 증권사 레퍼런스 간 정의가 다를 경우, 여러 출처에서 공통으로 확인되는 의미를 중심으로 설명한다.
4. LLM을 활용해 충돌 지점, 공통 의미, 서비스 문맥상 적절한 정의 후보를 도출한다.
5. 최종 설명은 투자 판단으로 오해될 표현을 제거하고 초보자 친화적으로 재작성한다.

출처 충돌이 큰 용어도 즉시 제외하지 않고, LLM 보조 판단과 사람 검수를 거쳐 최종 포함 여부를 결정한다.

최종 DB에는 충돌 검토에 활용한 모든 출처를 저장하지 않고, 최종 설명 작성에 가장 기준이 된 대표 출처 1개만 저장한다.

---

## 15. 데이터베이스 요구사항

### 15.1 DB 환경

| 항목 | 내용 |
|---|---|
| 초기 구축/검증 DB | SQLite |
| 최종 이관 DB | PostgreSQL |
| 클라우드 DB | Neon |
| 업데이트 방식 | 수동 업데이트 |
| 초기 운영 방식 | CSV 기반 수동 반영을 기본으로 하고, SQL seed 파일을 보조로 제공 |
| 향후 확장 | 관리자 페이지 또는 CMS 연동 가능 |

### 15.2 Neon 이관 방식

Neon 이관은 `schema.postgres.sql`로 대상 테이블을 먼저 생성한 뒤, `seed_terms.csv`를 `psql`의 `\copy` 명령으로 적재하는 방식을 기본으로 한다.

`seed_terms.sql`은 CSV 적재가 어려운 환경이나 수동 검토가 필요한 경우를 위한 보조 산출물로 제공한다.

Neon 이관 절차 문서인 `upload_to_neon.md`, `migration_to_neon.md`는 코드에서 생성하지 않는다. 두 문서는 실제 산출된 `schema.postgres.sql`, `seed_terms.csv`, `seed_terms.sql`, SQLite 검증 결과를 확인한 뒤 Codex가 직접 작성한다.

### 15.3 검색 요구사항

서비스에서는 다음 검색이 가능해야 한다.

| 검색 유형 | 설명 |
|---|---|
| 대표 용어 검색 | `매출`, `주가`, `공매도` 등 |
| 별칭 검색 | `PER`, `주가수익비율` 등 |
| 약어 검색 | `YoY`, `QoQ`, `YTD` 등 |
| 카테고리 검색 | 재무, 거래, 주가, 공시 등 |

---

## 16. LLM 프롬프트 정책

LLM 프롬프트는 하나의 통합 프롬프트로 구성하지 않고, 작업 목적별로 분리한다.

초기 구축에서는 다음 4개 프롬프트를 사용한다.

| 프롬프트 | 목적 |
|---|---|
| `definition_rewrite_prompt` | 용어, 별칭, 카테고리를 바탕으로 서비스용 설명문 생성 또는 정제 |
| `duplicate_alias_judgment_prompt` | 여러 용어가 같은 개념인지, 별칭으로 묶을 수 있는지, 별도 용어로 남겨야 하는지 판단 |
| `category_assignment_prompt` | 용어를 초기 고정 카테고리 중 하나로 분류 |
| `source_conflict_resolution_prompt` | 여러 출처의 정의가 다르거나 강조점이 다를 때 최종 설명 방향과 대표 출처 판단 |

`quality_review_prompt`는 별도 프롬프트로 두지 않는다. 품질 검토 기준은 각 프롬프트의 판단 기준과 사람 검수 단계에 포함한다.

실제 실행용 프롬프트 문안은 PRD 본문에 포함하지 않는다. 구현 단계에서 작성자가 본 문서의 판단 기준을 바탕으로 프롬프트를 작성하고, 샘플 데이터로 검증 및 평가를 반복하여 기준을 충족하는지 확인한 뒤 확정한다.

프롬프트 작성 기준에는 간결성을 포함한다. 간결성은 단순히 짧게 쓰는 것이 아니라, 출력 품질과 오류 방지에 직접 기여하는 지시만 남기는 것을 의미한다. 중복 지시, 같은 판단을 반복하는 few-shot, Pydantic 스키마가 이미 강제하는 내용을 과하게 설명하는 문장은 제거하거나 축약한다.

프롬프트는 별도 파일로 분리하여 관리한다.

```text
prompts/
  definition_rewrite.md
  duplicate_alias_judgment.md
  category_assignment.md
  source_conflict_resolution.md
```

모든 LLM 프롬프트의 출력은 JSON 형식으로 강제한다. 자유 텍스트 출력은 허용하지 않는다.

LLM 파이프라인은 LangChain과 LangGraph를 기반으로 구현한다. JSON 출력 강제와 파싱은 LangChain-Core의 `JsonOutputParser`와 Pydantic 모델을 사용한다.

LLM 파이프라인 실행 로그와 추적은 LangSmith를 사용한다. LangSmith 관련 설정값은 환경변수로 주입하며, 프롬프트 실행, 모델 응답, 파싱 실패, 재시도, `review_required_terms.csv` 분리 사유를 추적 가능한 형태로 남긴다.

LLM Provider는 Google을 사용한다. Google Gemini 모델 연동 패키지는 `langchain-google-genai`를 사용한다.

모델 호출 및 초기화는 Provider 변경 가능성을 고려하여 LangChain의 `init_chat_model`을 사용한다. 특정 Provider 클래스를 직접 초기화하는 방식은 1차 구현 기준에서 사용하지 않는다.

Google Gemini 모델을 사용할 때는 `google_genai` Provider를 명시한다. `gemini...` 모델명을 단독으로 전달하면 LangChain이 다른 Google Provider로 추론할 수 있으므로, `google_genai:gemini-3-flash`처럼 Provider prefix를 포함하거나 `model_provider="google_genai"`를 명시한다.

예:

```python
from langchain.chat_models import init_chat_model

llm = init_chat_model(
    "google_genai:gemini-3-flash",
    configurable_fields=("model", "model_provider"),
    temperature=0,
)
```

모델은 다음 기준으로 사용한다.

| 용도 | 모델 |
|---|---|
| Primary model | `gemini-3-flash` |
| Fallback/cost model | `gemini-3.1-flash-lite` |

Provider 변경이 필요한 경우에도 `init_chat_model`의 `model`, `model_provider` 설정을 교체하는 방식으로 대응한다. 보안상 `configurable_fields="any"`는 사용하지 않고, 필요한 필드만 명시한다.

모델 설정은 환경변수로 주입한다.

```text
GEMINI_API_KEY
MAIN_MODEL
FALLBACK_MODEL
DEFINITION_REWRITE_THINKING_LEVEL
DUPLICATE_ALIAS_JUDGMENT_THINKING_LEVEL
CATEGORY_ASSIGNMENT_THINKING_LEVEL
SOURCE_CONFLICT_RESOLUTION_THINKING_LEVEL
```

`MAIN_MODEL`의 기본값은 `gemini-3-flash`, `FALLBACK_MODEL`의 기본값은 `gemini-3.1-flash-lite`로 한다.

작업별 모델 추론 수준은 LangChain `init_chat_model` 호출 시 `thinking_level`로 지정한다.

| 작업 | thinking_level | 이유 |
|---|---:|---|
| `definition_rewrite_prompt` | `medium` | 설명 품질, 투자 조언 제거, 문맥 보존을 함께 판단해야 한다. |
| `duplicate_alias_judgment_prompt` | `medium` | 이름뿐 아니라 정의와 카테고리를 비교해야 한다. |
| `category_assignment_prompt` | `minimal` | 고정 카테고리 매핑 중심의 낮은 복잡도 작업이다. |
| `source_conflict_resolution_prompt` | `high` | 출처 간 정의 충돌과 대표 출처 판단의 오류 비용이 가장 크다. |

작업별 `thinking_level`은 `.env`에서 관리하고, 레포에는 `.env.example`로 작성 방향만 제공한다. `.env`는 실행 환경 파일이므로 코드 작업 중 임의로 수정하지 않는다.

LLM 파이프라인 검증 또는 비용 제어가 필요할 때는 수집 데이터를 재수집하지 않고 기존 `raw_terms.csv`를 사용하는 `existing` 모드와 처리 개수 제한 옵션을 사용한다.

### 16.1 주요 프레임워크 버전

주요 Python 패키지는 2026-05-12 기준 PyPI 최신 버전으로 정확히 고정한다.

```text
scrapling[all]==0.4.8
langchain==1.2.18
langchain-core==1.4.0
langgraph==1.1.10
langchain-google-genai==4.2.2
pydantic==2.13.4
```

각 프롬프트는 목적별 Pydantic 출력 스키마를 가진다. LLM 응답이 스키마를 만족하지 못하거나 파싱에 실패한 경우 해당 항목은 자동 반영하지 않고 재시도하거나 `review_required_terms.csv`에 기록한다.

JSON 파싱 실패 또는 Pydantic 스키마 검증 실패 시 재시도 정책은 다음과 같다.

1. 1차 실패 시 동일 입력으로 JSON 형식 수정 요청을 보낸다.
2. 2차 실패 시 한 번 더 재시도한다.
3. 3차 실패 시 자동 처리를 중단하고 `review_required_terms.csv`에 기록한다.

재시도 후에도 유효한 JSON과 스키마를 만족하지 못한 결과는 최종 DB에 반영하지 않는다.

### 16.2 `definition_rewrite_prompt`

`definition_rewrite_prompt`는 수집된 용어를 국내주식 서비스의 툴팁/설명용 문장으로 작성하거나 정제하는 데 사용한다.

전문 용어를 무조건 쉬운 말로 바꾸지 않는다. 주식 용어 사전의 목적은 전문 용어를 없애는 것이 아니라, 전문 용어의 정확한 의미와 사용 맥락을 사용자가 따라갈 수 있게 설명하는 것이다.

입력은 최종 DB의 설명 작성에 필요한 최소 컬럼만 사용한다.

```text
term
aliases
category
current_definition
```

`current_definition`은 수집 및 전처리를 거쳐 현재 항목에 들어 있는 기존 정의다. 데이터 컬럼명은 `definition`을 유지하되, 프롬프트 입력에서는 기존 정의임을 명확히 하기 위해 `current_definition`으로 전달한다.

`source_name`과 `source_url`은 이 프롬프트의 입력으로 사용하지 않는다. 출처 정보는 설명 생성이 아니라 검수와 대표 출처 선택에 사용한다.

출력은 다음 JSON 필드만 사용한다.

```text
decision
definition
```

`decision`은 `rewritten` 또는 `uncertain` 중 하나다. `uncertain`이면 `definition`은 빈 문자열로 둔다. 검토 사유는 파이프라인이 `review_required_terms.csv`의 로그 컬럼에 남긴다.

판단 기준은 다음과 같다.

- 새 정의를 창작하지 않고 `current_definition`의 의미 범위 안에서 서비스용 설명으로 다시 쓴다.
- 첫 문장에서 해당 용어의 핵심 의미를 직접 설명한다.
- 전문 용어를 피하지 않는다. 다만 설명 대상 용어보다 더 어려운 용어를 불필요하게 늘어놓지 않는다.
- 국내주식 서비스 문맥에 맞는 설명으로 작성한다.
- 뉴스, 재무제표, 공시, 리포트, 주가 화면 중 어디에서 쓰이는지 드러나야 한다.
- 계산식이나 비교 기준이 중요한 용어는 `current_definition`에 있는 범위에서 포함한다.
- `current_definition`에 없는 세부 수치, 법적 요건, 계산식, 보호 여부, 상품 조건은 추가하지 않는다.
- 투자 판단, 매수/매도 권유, 수익 보장처럼 읽힐 표현은 제거한다.
- 긍정/부정 해석이 가능한 용어는 조건과 한계를 함께 설명한다.
- `current_definition`만으로 의미를 특정하기 어렵거나 안전하게 다시 쓸 수 없으면 `decision`을 `uncertain`으로 둔다.
- 설명은 짧게 제한하기보다, 하나의 툴팁에서 자연스럽게 읽을 수 있도록 작성한다.
- 예시가 이해에 도움이 되는 용어는 간단한 예시를 포함한다.
- 프롬프트 문안은 위 판단에 필요한 내용만 남기고, 같은 기준을 여러 섹션에서 반복하지 않는다.

Few-shot 예시는 다음과 같다.

입력:

```text
term: PER
aliases: ["주가수익비율", "P/E Ratio"]
category: 투자지표/밸류에이션
current_definition: 주가를 주당순이익으로 나눈 투자지표
```

좋은 출력:

> PER는 주가를 주당순이익(EPS)으로 나눈 투자지표입니다. 기업이 벌어들이는 이익에 비해 주가가 어느 정도 수준인지 볼 때 사용합니다. PER가 낮다고 항상 저평가라는 뜻은 아니며, 업종 특성이나 성장성에 따라 다르게 해석될 수 있습니다.

입력:

```text
term: 권리락
aliases: []
category: 공시/기업행위
current_definition: 배당이나 증자 권리를 받을 수 없게 된 상태
```

좋은 출력:

> 권리락은 주식을 사도 유상증자, 무상증자, 배당 같은 특정 권리를 받을 수 없게 된 상태를 뜻합니다. 권리락일에는 해당 권리의 가치가 빠진 만큼 주가 기준이 조정될 수 있습니다. 주가가 내려 보이더라도 단순한 악재로만 해석하면 안 됩니다.

입력:

```text
term: YoY
aliases: ["Year on Year", "전년 동기 대비"]
category: 리포트/실적 표현
current_definition: 전년 같은 기간과 비교한다는 뜻
```

좋은 출력:

> YoY는 전년 같은 기간과 비교한다는 뜻입니다. 예를 들어 2026년 2분기 매출의 YoY 증감률은 2025년 2분기 매출과 비교해 계산합니다. 실적 기사나 리포트에서 계절 영향을 줄이고 성장 흐름을 볼 때 자주 사용됩니다.

### 16.3 `duplicate_alias_judgment_prompt`

`duplicate_alias_judgment_prompt`는 수집된 여러 용어가 같은 개념인지, 별칭으로 묶을 수 있는지, 별도 용어로 남겨야 하는지 판단하는 데 사용한다.

입력은 용어명만 사용하지 않고, 판단에 필요한 최소 맥락을 함께 전달한다.

```text
candidates:
  term
  definition
  category
```

별칭으로 묶는 기준은 다음과 같다.

- 약어와 전체 명칭 관계다. 예: `PER` / `주가수익비율`
- 한글명과 영문명 관계다. 예: `자기자본이익률` / `ROE`
- 한글명과 영문명 또는 약어가 괄호 표현으로 함께 등장한다. 예: `ELS(주가연계증권)`
- 같은 계산식, 같은 대상, 같은 사용 맥락을 가진다.

띄어쓰기만 다른 표현은 aliases에 포함하지 않고, 검색 또는 매칭 단계의 정규화 대상으로 본다.

별도 용어로 분리하는 기준은 다음과 같다.

- 한쪽이 다른 쪽보다 넓거나 좁은 개념이다.
- 발생 조건이나 계산 방식이 다르다.
- 투자자가 해석할 때 다른 의미로 쓰인다.
- 뉴스에서 함께 등장하더라도 설명해야 할 포인트가 다르다.
- 비슷한 말이지만 제도상 의미가 다르다.

판단 결과는 `alias`, `separate`, `uncertain` 중 하나로 구분한다. `uncertain`은 억지 병합을 막기 위해 허용한다.

출력은 다음 JSON 필드만 사용한다.

```text
decision
representative_term
aliases
```

`separate`와 `uncertain`이면 입력 후보를 그대로 유지하면 되므로 별도 유지 목록은 출력하지 않는다.

프롬프트 문안은 별칭/분리/불확실성 판단에 필요한 기준과 대표 사례 중심으로 유지하고, 유사한 예시는 반복하지 않는다.

### 16.4 `category_assignment_prompt`

`category_assignment_prompt`는 용어를 재설계한 고정 카테고리 중 하나로 분류하는 데 사용한다.

입력은 다음 필드만 사용한다.

```text
term
definition
```

분류 기준은 다음과 같다.

- 용어가 재무제표 항목이나 회계 개념이면 `재무/회계`를 우선한다.
- 계산 지표나 밸류에이션 지표면 `투자지표/밸류에이션`을 우선한다.
- 주문, 체결, 호가, 신용거래, 결제 흐름이면 `거래/주문/결제`를 우선한다.
- 가격 자체, 시세 화면 값, 차트/기술적 지표면 `가격/차트`를 우선한다.
- 시장 구분, 상장, 종목 지위 관련이면 `시장/상장`을 우선한다.
- 공시, 증자, 감자, 합병, 분할, 자기주식 등 기업 이벤트면 `공시/기업행위`를 우선한다.
- 배당 정책이나 주주환원이 핵심이면 `배당/주주환원`을 우선한다.
- 개인/기관/외국인, 순매수/순매도 등 매매 주체 흐름이면 `수급/투자자`를 우선한다.
- 실적 발표, 컨센서스, 목표주가, 투자의견 표현이면 `리포트/실적 표현`을 우선한다.
- ETF, ETN, 리츠, 펀드, 집합투자기구면 `ETF/펀드`를 우선한다.
- ELS, DLS, ELB, DLB, 선물, 옵션, 스왑 등 파생 또는 구조화 상품이면 `파생/구조화상품`을 우선한다.
- 채권, 회사채, 국채, 금리, 환율, 외환 흐름이면 `채권/금리/환율`을 우선한다.
- 물가, 경기, GDP, 인플레이션처럼 종목보다 시장 환경을 설명하면 `거시경제`를 우선한다.
- 위 기준으로도 결정하기 어렵거나 주식 뉴스 큐레이션 목적과 거리가 멀면 `기타`로 둔다.

출력은 다음 JSON 필드만 사용한다.

```text
category
```

후속 처리에서 사용하지 않는 보조 카테고리와 판단 메모는 출력하지 않는다. `기타`는 최종 카테고리가 아니라 다음 LLM 단계로 넘기지 않을 제외용 임시 카테고리다.

프롬프트 문안은 카테고리 목록, 우선순위, 필요한 경계 사례 중심으로 유지하고, 카테고리 설명을 장황하게 반복하지 않는다.

### 16.5 `source_conflict_resolution_prompt`

`source_conflict_resolution_prompt`는 여러 출처의 정의가 다르거나 강조점이 다를 때, 최종 설명에 어떤 의미를 반영할지 판단하는 데 사용한다.

입력은 URL을 제외하고, 대표 출처 매핑에 필요한 식별자와 판단에 필요한 텍스트만 전달한다.

```text
term
sources:
  source_id
  source_name
  definition
```

`source_url`은 LLM 판단 근거로 사용하지 않는다. 최종 DB의 대표 출처 URL은 파이프라인이 `representative_source_id`를 원본 출처 목록에 매핑해 채운다.

판단 기준은 다음과 같다.

- 공식 기관 출처와 1차 레퍼런스의 정의를 먼저 비교한다.
- 여러 출처가 공통으로 말하는 의미를 최종 정의의 중심에 둔다.
- 특정 출처에만 있는 부가 설명은 국내주식 서비스에서 자주 쓰이는 경우에만 반영한다.
- 회계/공시/제도 용어는 공식적 의미를 우선한다.
- 리포트/뉴스 관용 표현은 실제 사용 맥락을 우선한다.
- 출처 간 충돌이 계산식, 제도 요건, 법적 의미 차이라면 `uncertain`으로 표시한다.
- 최종 설명에는 충돌 자체를 길게 설명하지 않고, 사용자에게 필요한 핵심 의미만 남긴다.

판단 결과는 `resolved`, `uncertain` 중 하나로 구분한다. `uncertain`이면 최종 DB에 바로 반영하지 않고 `review_required_terms.csv`에 기록한다.

출력은 다음 JSON 필드만 사용한다.

```text
decision
recommended_definition
representative_source_id
```

출처 간 차이 요약과 판단 근거는 LLM 출력에 포함하지 않는다. `uncertain`이면 `recommended_definition`과 `representative_source_id`는 빈 문자열로 둔다.

프롬프트 문안은 대표 출처 선택, 충돌 해결, 불확실성 분리에 필요한 기준만 남기고, 출처 신뢰도 설명을 반복하지 않는다.

---

## 17. 카테고리 정책

초기 구축에서는 아래 고정 카테고리를 사용한다.

아래 목록은 중복 제거된 수집 데이터 1,600건의 분포를 확인한 뒤, 주식 뉴스 큐레이션 목적에 맞게 재설계한 카테고리다.

| 카테고리 | 예시 |
|---|---|
| 주식 기초 | 주식, 종목, 주가, 매수, 매도 |
| 시장/상장 | 코스피, 코스닥, IPO, 상장, 관리종목 |
| 가격/차트 | 시가, 고가, 저가, 종가, 이동평균선, 갭 |
| 거래/주문/결제 | 주문, 체결, 호가, 공매도, 신용거래, 결제 |
| 공시/기업행위 | 공시, 증자, 감자, 합병, 분할, 자사주 |
| 재무/회계 | 매출, 영업이익, 당기순이익, 자산, 부채 |
| 투자지표/밸류에이션 | PER, PBR, ROE, EPS, BPS, EV/EBITDA |
| 실적/리포트 표현 | YoY, QoQ, 컨센서스, 어닝 쇼크 |
| 수급/투자자 | 개인, 기관, 외국인, 순매수, 순매도 |
| 배당/주주환원 | 배당금, 배당수익률, 배당락 |
| ETF/펀드 | ETF, ETN, 리츠, MMF, 펀드 |
| 파생/구조화상품 | ELS, DLS, ELB, DLB, 선물, 옵션, 스왑 |
| 채권/금리/환율 | 채권, 국채, 회사채, 금리, 환율 |
| 거시경제 | 물가, 경기, GDP, 인플레이션 |
| 기타 | 다음 단계로 넘기지 않을 제외용 임시 카테고리 |

`기타`는 최종 DB 카테고리가 아니다. `category_assignment_prompt` 이후 게이트 단계에서 `기타` 항목은 다음 LLM 단계로 넘기지 않고 별도 CSV로 분리한다.

---

## 18. 성공 기준

| 기준 | 목표 |
|---|---|
| 기본 용어 커버리지 | 전처리 후 유효 용어 수가 100개를 초과하고 국내주식 웹 서비스 핵심 용어를 설명 가능 |
| 출처 기록률 | 최종 용어 100% 출처 URL 기록 |
| 설명 일관성 | 모든 용어가 동일한 설명 스타일 가이드 준수 |
| 주린이 친화성 | 초보자가 이해 가능한 문장으로 작성 |
| 범위 통제 | 과도한 금융상품 용어 유입 방지 |
| 확장 가능성 | LLM 기반 용어 추가가 가능한 데이터 구조 확보 |

---

## 19. 미정 사항

| 항목 | 현재 상태 |
|---|---|
| 최종 카테고리 | 초기 고정 카테고리로 수집 후, 실제 용어 분포를 보고 재설계 가능 |
| LLM 프롬프트 상세 문안 | PRD에는 포함하지 않고, 구현 단계에서 작성·검증·평가 반복 후 별도 파일로 확정 |

---

## 20. 현재 결정 사항 요약

- 주식 용어 사전은 국내주식 웹 서비스의 툴팁용으로 구축한다.
- 주요 사용자는 주식 초보자, 주린이다.
- 설명은 짧음보다 명확성을 우선한다.
- 최종 산출물은 `stock_dictionary.sqlite`, `schema.postgres.sql`, `seed_terms.csv`, `seed_terms.sql`, `upload_to_neon.md`, `migration_to_neon.md`로 한다.
- `upload_to_neon.md`, `migration_to_neon.md`는 코드 자동 생성 대상이 아니며, Codex가 최종 산출물 확인 후 직접 작성한다.
- Neon 이관은 `schema.postgres.sql`로 테이블을 생성한 뒤 `seed_terms.csv`를 `psql \copy`로 적재하는 방식을 기본으로 한다.
- 초기 용어 개수는 사전에 고정하지 않고, 전처리 후 유효 용어 수가 100개 이하가 아니라면 계속 진행한다.
- DB는 단일 테이블 중심으로 구성한다.
- 필수 컬럼은 `id`, `term`, `aliases`, `category`, `definition`, `source_name`, `source_url`, `created_at`, `updated_at`로 한다.
- `aliases`는 JSON 배열 형태로 관리한다. SQLite에서는 JSON 배열 문자열 `TEXT`로 저장하고, PostgreSQL/Neon에서는 `JSONB`로 이관한다.
- 별칭이 없는 용어의 `aliases`는 항상 `[]`로 저장한다.
- 최종 DB에는 대표 출처 1개만 저장한다.
- 초기 카테고리는 고정 목록을 사용하되, 수집된 데이터를 확인한 뒤 재설계할 수 있다.
- 데이터 수집은 Scrapling 기반 파이프라인으로 구축하고, 전처리 및 LLM 보조 정제 파이프라인을 거쳐 `cleaned_terms.csv`와 SQLite DB를 생성한다.
- LLM 개입 흔적은 최종 DB 컬럼에 남기지 않는다.
- 사람 검수가 필요한 항목은 `review_required_terms.csv` CSV 로그에 기록한다.
- 사람 검수는 파이프라인 내 Human-in-the-loop로 구현하지 않고 프로젝트 담당자가 별도로 수동 진행한다.
- 실제 수집 실행 중 실패한 레퍼런스는 `scrape_failures.csv`에 간단한 로그를 남긴다.
- 파이프라인 파일 구조는 `scripts/`, `data/`, `output/` 3개 디렉터리를 기준으로 구성한다.
- `raw_terms.csv`는 `term`, `raw_definition`, `source_name`, `source_url`, `collected_at` 컬럼을 사용한다.
- `cleaned_terms.csv`는 `term`, `aliases`, `category`, `definition`, `source_name`, `source_url` 컬럼을 사용한다.
- 대표 용어는 국내주식 서비스에서 자주 보일 표현을 우선하되, 널리 쓰이는 약어는 약어를 대표 용어로 사용한다.
- 기본 용어는 기존 용어 사전 레퍼런스에서 수집한다.
- 레퍼런스는 KB증권, 금융위원회, 미래에셋증권, iM증권, 한국투자증권, KDI, 신한투자증권을 사용한다.
- 기획재정부 시사경제용어사전은 현재 레퍼런스에서 제외한다.
- YoY, QoQ, YTD 같은 용어는 1차 레퍼런스 수집 이후 LLM 기반 보완 및 정제 단계에서 작성한다.
- LLM은 미흡한 용어 정의 보완, 중복 판단, 별칭 판단, 카테고리 판단, 출처 충돌 해석, 설명 품질 개선에 활용한다.
- LLM 프롬프트는 `definition_rewrite_prompt`, `duplicate_alias_judgment_prompt`, `category_assignment_prompt`, `source_conflict_resolution_prompt` 4개로 분리한다.
- 실제 실행용 프롬프트 문안은 PRD에 포함하지 않고, `prompts/` 디렉터리의 별도 파일로 관리한다.
- 프롬프트는 구현 단계에서 작성자가 판단 기준을 바탕으로 작성하고, 샘플 데이터로 검증 및 평가를 반복한 뒤 확정한다.
- `definition_rewrite_prompt`의 입력은 `term`, `aliases`, `category`, `current_definition`만 사용한다.
- LLM 프롬프트 출력은 JSON으로 강제하고, LangChain/LangGraph 기반 파이프라인에서 LangChain-Core `JsonOutputParser`와 Pydantic 모델로 검증한다.
- LLM 파이프라인 로깅과 추적은 LangSmith를 사용한다.
- LLM Provider는 Google을 사용하고, Google Gemini 연동 패키지는 `langchain-google-genai`를 사용한다.
- 모델 호출/초기화는 Provider 변경 가능성을 위해 LangChain `init_chat_model`을 사용한다.
- Primary model은 `gemini-3-flash`, Fallback/cost model은 `gemini-3.1-flash-lite`로 한다.
- LLM 환경변수는 `GEMINI_API_KEY`, `MAIN_MODEL`, `FALLBACK_MODEL`, 작업별 `*_THINKING_LEVEL`을 사용한다.
- 주요 프레임워크 버전은 `scrapling[all]==0.4.8`, `langchain==1.2.18`, `langchain-core==1.4.0`, `langgraph==1.1.10`, `langchain-google-genai==4.2.2`, `pydantic==2.13.4`로 고정한다.
- JSON 파싱 또는 Pydantic 검증 실패 시 최대 2회 재시도하고, 3차 실패 시 `review_required_terms.csv`에 기록한다.
- 출처 충돌이 큰 용어도 즉시 제외하지 않고 LLM 보조 판단과 사람 검수를 거쳐 포함 여부를 결정한다.
- 모든 용어는 출처 URL을 기록한다.
- DB는 SQLite로 먼저 구축·검증한 뒤 PostgreSQL/Neon으로 이관하며, 업데이트는 수동으로 진행한다.
