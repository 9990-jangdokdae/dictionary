# Neon 업로드 절차

이 문서는 로컬에서 검증된 주식 용어 사전 산출물을 Neon PostgreSQL에 업로드하기 위한 수동 절차다.

## 대상 산출물

- `output/schema.postgres.sql`
- `output/seed_terms.csv`
- `output/seed_terms.sql`
- `output/stock_dictionary.sqlite`

현재 검증 기준:

- `data/cleaned_terms.csv`: 1,436개 데이터 행
- SQLite `stock_terms`: 1,436개 행
- SQLite `aliases` JSON 검증 실패: 0개

## 1. 접속 정보 준비

Neon 프로젝트에서 PostgreSQL 접속 문자열을 확인한 뒤 로컬 셸에 설정한다.

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
```

## 2. 스키마 생성

기존 `stock_terms` 테이블이 있는 환경이라면 먼저 백업하거나 staging 데이터베이스에서 검증한다.

```bash
psql "$DATABASE_URL" -f output/schema.postgres.sql
```

## 3. CSV 적재

`seed_terms.csv`를 `psql`의 `\copy`로 적재한다. `aliases` 컬럼은 PostgreSQL에서 `JSONB`로 저장된다.

```bash
psql "$DATABASE_URL"
```

```sql
\copy stock_terms (term, aliases, category, definition, source_name, source_url)
FROM 'output/seed_terms.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
```

## 4. 적재 검증

```sql
SELECT COUNT(*) FROM stock_terms;
SELECT COUNT(*) FROM stock_terms WHERE jsonb_typeof(aliases) <> 'array';
SELECT category, COUNT(*) FROM stock_terms GROUP BY category ORDER BY COUNT(*) DESC;
SELECT term, aliases, category, definition FROM stock_terms ORDER BY id LIMIT 5;
```

기대값:

- `COUNT(*)`: 1,436
- `jsonb_typeof(aliases) <> 'array'`: 0
- `category = '기타'`: 0

## 5. 대체 적재 방식

CSV 업로드가 어려운 환경에서는 `output/seed_terms.sql`을 사용할 수 있다.

```bash
psql "$DATABASE_URL" -f output/seed_terms.sql
```

대량 데이터에서는 CSV `\copy`가 기본 방식이며, `seed_terms.sql`은 수동 검토나 제한된 환경을 위한 보조 산출물로 사용한다.
