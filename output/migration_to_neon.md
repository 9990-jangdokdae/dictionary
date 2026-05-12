# SQLite 검증 결과를 Neon으로 이관하는 기준

이 문서는 로컬 SQLite 검증 결과를 Neon/PostgreSQL에 이관할 때 확인해야 할 기준을 정리한 수동 가이드다.

## 로컬 검증 결과

현재 최종 산출물은 다음 기준을 통과했다.

- `data/cleaned_terms.csv`: 1,436개 데이터 행
- `output/stock_dictionary.sqlite`: 생성 완료
- SQLite `stock_terms`: 1,436개 행
- `aliases` JSON 검증 실패: 0개
- 최종 포함된 `기타` 카테고리: 0개
- term 중복: 0개

로컬 검증 SQL:

```sql
SELECT COUNT(*) FROM stock_terms;
SELECT COUNT(*) FROM stock_terms WHERE NOT json_valid(aliases);
SELECT COUNT(*) FROM stock_terms WHERE category = '기타';
SELECT term, COUNT(*) FROM stock_terms GROUP BY term HAVING COUNT(*) > 1;
```

## 이관 대상 파일

- `output/schema.postgres.sql`: Neon/PostgreSQL 테이블 생성 SQL
- `output/seed_terms.csv`: 기본 적재 파일
- `output/seed_terms.sql`: 보조 적재 파일
- `data/review_required_terms.csv`: 자동 반영하지 않은 검수 후보 20개
- `data/category_excluded_terms.csv`: category gate에서 제외한 145개
- `data/llm_full/`: LLM 단계별 실행 로그

## Neon 반영 기준

1. `schema.postgres.sql`로 `stock_terms` 테이블을 생성한다.
2. `seed_terms.csv`를 `psql \copy`로 적재한다.
3. Neon의 `stock_terms` row count가 로컬 SQLite row count와 일치해야 한다.
4. `aliases`는 JSONB 배열이어야 한다.
5. 최종 DB에는 `기타` 카테고리를 포함하지 않는다.

Neon 검증 SQL:

```sql
SELECT COUNT(*) FROM stock_terms;
SELECT COUNT(*) FROM stock_terms WHERE jsonb_typeof(aliases) <> 'array';
SELECT COUNT(*) FROM stock_terms WHERE category = '기타';
SELECT term, COUNT(*) FROM stock_terms GROUP BY term HAVING COUNT(*) > 1;
```

기대값:

- `COUNT(*)`: 1,436
- JSONB 배열 오류: 0
- `기타` 카테고리: 0
- 중복 term: 0

## 운영 주의사항

- 최종 DB에는 LLM 개입 여부, 프롬프트 판단 메모, 검수 메모를 컬럼으로 남기지 않는다.
- 출처는 최종 설명 작성 기준이 된 대표 `source_name`, `source_url` 1개만 저장한다.
- `data/review_required_terms.csv`의 20개 항목은 자동 반영하지 않은 항목이다.
- 기존 Neon 테이블이 있다면 운영 반영 전 staging 테이블 또는 별도 브랜치에서 먼저 검증한다.
