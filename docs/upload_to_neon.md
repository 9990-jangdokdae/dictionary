# Neon 업로드 절차

이 문서는 기존 Neon PostgreSQL 데이터베이스에 주식 용어 사전 테이블 `stock_terms`를 추가하는 수동 절차다.

`output/schema.postgres.sql`은 `stock_terms` 테이블만 생성한다. 기존 데이터베이스의 다른 테이블이나 스키마는 변경하지 않는다. 다만 같은 이름의 `stock_terms` 테이블이 이미 있으면 `CREATE TABLE stock_terms` 실행은 실패하므로, 적용 전에 반드시 테이블 존재 여부를 확인한다.

## 대상 산출물

| 파일 | 용도 |
| --- | --- |
| `output/schema.postgres.sql` | `stock_terms` 테이블 생성 SQL |
| `output/seed_terms.csv` | CSV 적재용 데이터 |
| `output/seed_terms.sql` | SQL Editor 또는 제한된 환경에서 사용할 보조 적재 SQL |
| `output/stock_dictionary.sqlite` | 로컬 검증용 SQLite DB |

현재 검증 기준:

| 항목 | 값 |
| --- | ---: |
| `data/cleaned_terms.csv` 데이터 행 | 1,409 |
| SQLite `stock_terms` 행 | 1,409 |
| SQLite `aliases` JSON 검증 실패 | 0 |

## 1. Neon SQL Editor 열기

1. Neon Console에 접속한다.
2. 대상 Project와 Branch를 선택한다.
3. 좌측 또는 상단 메뉴에서 SQL Editor를 연다.
4. 아래 SQL을 순서대로 붙여 넣고 실행한다.

운영 DB에 바로 적용하기보다 Neon branch 또는 staging DB에서 먼저 실행하고 검증하는 것을 권장한다.

## 2. 기존 스키마 확인

먼저 현재 DB에 `stock_terms` 테이블이 이미 있는지 확인한다.

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

`stock_terms`만 빠르게 확인하려면 다음 SQL을 실행한다.

```sql
SELECT EXISTS (
  SELECT 1
  FROM information_schema.tables
  WHERE table_schema = 'public'
    AND table_name = 'stock_terms'
) AS stock_terms_exists;
```

결과가 `false`이면 새 테이블을 생성해도 된다.

결과가 `true`이면 바로 다음 단계로 진행하지 않는다. 기존 테이블의 용도와 데이터를 확인한 뒤 다음 중 하나를 선택한다.

| 선택지 | 설명 |
| --- | --- |
| 기존 테이블 유지 | 이미 서비스에서 사용 중이라면 새 업로드를 중단하고 별도 계획을 세운다. |
| 백업 후 교체 | 기존 `stock_terms`를 백업 테이블로 rename한 뒤 새로 생성한다. |
| staging 테이블 사용 | `stock_terms_staging` 같은 임시 테이블에 먼저 적재하고 검증한다. |
| append/merge | 기존 데이터에 추가하는 방식이 필요한 경우 중복 기준과 upsert 정책을 별도로 정한다. |

## 3. 스키마 생성

`output/schema.postgres.sql` 파일 내용을 SQL Editor에 붙여 넣고 실행한다.

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

생성 후 테이블 구조를 확인한다.

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'stock_terms'
ORDER BY ordinal_position;
```

## 4. 데이터 적재

권장 방식은 환경에 따라 다르다.

| 방식 | 사용 상황 |
| --- | --- |
| Neon Console의 CSV import 기능 | Console에서 CSV 업로드를 지원하고 파일 업로드가 가능한 경우 |
| `psql \copy` | 로컬에서 접속 문자열과 `psql`을 사용할 수 있는 경우 |
| `seed_terms.sql` | SQL Editor에서 직접 실행해야 하는 경우 |

### 4.1 CSV import 또는 `psql \copy`

CSV 방식은 `output/seed_terms.csv`를 사용한다. 컬럼 순서는 다음과 같다.

```text
term, aliases, category, definition, source_name, source_url
```

`psql`을 사용할 수 있다면 다음처럼 실행한다. `\copy`는 SQL Editor 명령이 아니라 `psql` 클라이언트 명령이다.

```bash
psql "$DATABASE_URL"
```

```sql
\copy stock_terms (term, aliases, category, definition, source_name, source_url)
FROM 'output/seed_terms.csv'
WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
```

### 4.2 SQL Editor에서 `seed_terms.sql` 실행

SQL Editor만 사용할 수 있다면 `output/seed_terms.sql` 파일 내용을 SQL Editor에 붙여 넣고 실행한다.

파일 크기나 SQL Editor 제한으로 실행이 어렵다면 CSV import 또는 `psql \copy` 방식으로 전환한다.

## 5. 적재 검증

적재 후 SQL Editor에서 다음 쿼리를 실행한다.

```sql
SELECT COUNT(*) FROM stock_terms;
```

```sql
SELECT COUNT(*) AS invalid_aliases
FROM stock_terms
WHERE jsonb_typeof(aliases) <> 'array';
```

```sql
SELECT COUNT(*) AS misc_category_count
FROM stock_terms
WHERE category = '기타';
```

```sql
SELECT term, COUNT(*)
FROM stock_terms
GROUP BY term
HAVING COUNT(*) > 1;
```

```sql
SELECT term, aliases, category, definition
FROM stock_terms
ORDER BY id
LIMIT 5;
```

기대값:

| 항목 | 기대값 |
| --- | ---: |
| `COUNT(*)` | 1,409 |
| `invalid_aliases` | 0 |
| `misc_category_count` | 0 |
| 중복 term 조회 결과 | 0행 |

## 6. 운영 반영 전 확인

운영 DB에 반영하기 전 다음을 확인한다.

- 기존 서비스 테이블과 이름이 충돌하지 않는다.
- `stock_terms`를 참조하는 애플리케이션 쿼리가 단일 테이블 구조와 맞는다.
- `aliases`는 PostgreSQL에서 `JSONB` 배열로 적재되었다.
- row count가 로컬 검증 결과와 일치한다.
- staging 또는 Neon branch에서 동일 절차를 먼저 검증했다.
