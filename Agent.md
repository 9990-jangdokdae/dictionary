# Agent Guide

주식 용어 사전 파이프라인을 수정할 때 지켜야 할 작업 기준이다.

## 1. 환경 파일

- `.env`는 수정하지 않는다.
- 환경 변수의 예시는 `.env.example`에만 작성한다.
- 모델명, API 키, LangSmith 설정, 작업별 `*_THINKING_LEVEL`은 실행 환경 값으로 다룬다.

## 2. 전처리의 책임

전처리는 구조 정리만 담당한다.

허용:
- 공백 정리
- 반복 괄호 제거
- 명백한 노이즈 제거
- 동일 별칭 그룹 병합
- CSV/JSON 형식 보존

금지:
- 특정 실패 샘플명을 규칙에 추가해 테스트를 통과시키는 것
- 카테고리, 별칭, 출처 우선순위 같은 의미 판단을 키워드 나열로 우회하는 것
- PRD에서 제외 또는 후순위로 둔 금융상품을 규칙으로 억지 포함시키는 것

## 3. 의미 판단의 책임

의미 판단은 LLM 단계에서 처리한다.

- 설명 정제: `definition_rewrite`
- 카테고리 판단: `category_assignment`
- 중복/별칭 판단: `duplicate_alias_judgment`
- 출처 충돌 판단: `source_conflict_resolution`

LLM 출력은 프롬프트와 Pydantic 스키마에 정의된 최소 필드만 사용한다. 최종 DB에 남기지 않을 판단 메모는 LLM 출력에 포함하지 않는다.

## 4. 대표 샘플 원칙

대표 샘플은 검증 도구이지 구현 대상이 아니다.

- 샘플 실패 시 샘플명을 규칙에 넣지 않는다.
- 실패 원인을 일반화하고 책임 단계를 먼저 정한다.
- 구조 문제는 전처리에서 고친다.
- 의미 판단 문제는 LLM 단계 연결, 프롬프트, 스키마 개선으로 고친다.

## 5. 현재 남은 정석 작업

- `category_assignment`를 실제 파이프라인에 연결한다.
- `duplicate_alias_judgment`를 실제 파이프라인에 연결한다.
- `source_conflict_resolution`을 실제 파이프라인에 연결한다.
- 각 단계 연결 후 대표 샘플 검증을 다시 수행한다.

## 6. Neon 문서 작성 경계

- `upload_to_neon.md`, `migration_to_neon.md`는 코드 자동 생성 대상이 아니다.
- exporter, pipeline, 테스트는 두 문서 생성을 기대하거나 구현하지 않는다.
- 두 문서는 최종 `schema.postgres.sql`, `seed_terms.csv`, `seed_terms.sql`, SQLite 검증 결과를 확인한 뒤 Codex가 직접 작성한다.

## 7. 완료 기준

- `uv run pytest -q`가 통과한다.
- 프롬프트 출력 계약과 Pydantic 스키마가 일치한다.
- 남은 warning은 우리 코드 문제인지 외부 의존성 문제인지 구분되어 있다.
