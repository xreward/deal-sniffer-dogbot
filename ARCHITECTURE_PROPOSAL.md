# Deal Hub Platform Architecture Proposal

## 1) Goal

`deal-hub-platform`은 핫딜/가격추적을 중심으로 시작하되, 이후 리워드/공구까지 확장 가능한 구조를 목표로 한다.

핵심 방향:

1. 사이트별 크롤러/파서 로직은 분리
2. DB 세션/인프라 연결은 공통
3. 테이블(스키마)은 사이트별 + 코어 도메인 분리
4. 오케스트레이션/워크플로우는 공통 파이프라인으로 관리

---

## 2) Recommended Repository Structure (Simple First)

아래 구조를 v1 기준으로 추천한다.

```text
deal-hub-platform/
  README.md
  pyproject.toml
  .env.example

  src/
    settings.py
    main.py

    common/
      db.py
      queue.py
      logging.py
      types.py

    sites/
      coupang/
        crawler.py
        parser.py
        repository.py
      site_x/
        crawler.py
        parser.py
        repository.py

    jobs/
      ingest.py
      evaluate.py
      notify.py

  migrations/
    core/
    coupang/
    site_x/

  tests/
    unit/
    integration/
```

---

## 3) System Architecture

### 3.1 Layers

1. `sites/*`: 사이트별 수집/파싱/저장 구현
2. `common/*`: 공통 DB 세션, 큐 클라이언트, 공통 타입/로깅
3. `jobs/*`: 파이프라인 실행 단위(수집/평가/알림)
4. `migrations/*`: 코어 및 사이트별 스키마 진화 관리

### 3.2 Data Flow

1. `ingest job`이 사이트 URL/작업을 큐에 적재
2. 사이트별 crawler가 raw payload(HTML/API 응답)를 수집
3. 사이트별 parser가 canonical product/deal 이벤트로 정규화
4. repository가 공통 세션으로 DB 저장
5. evaluate job이 hotdeal 규칙을 평가
6. notify job이 텔레그램/외부 채널로 전달

---

## 4) Database Strategy

### 4.1 One Session, Multiple Schemas

공통 SQLAlchemy engine/session은 하나로 유지한다.  
대신 테이블은 아래처럼 분리한다.

1. `core.*`: 공통 도메인
2. `coupang.*`: 쿠팡 전용
3. `site_x.*`: 타 사이트 전용

### 4.2 Core vs Site Responsibility

`core` 예시:

1. `core.crawl_jobs`
2. `core.normalized_products`
3. `core.hotdeals`
4. `core.notifications_outbox`

`site` 예시:

1. `coupang.product_snapshots`
2. `coupang.price_history`
3. `site_x.raw_items`

이 구조로 가면 사이트 추가 시 `sites/site_y` + `migrations/site_y`만 추가하면 된다.

---

## 5) Queue/Event Contract

큐 payload는 사이트 종속 필드와 공통 필드를 분리한다.

공통 필드 예시:

1. `site`
2. `job_id`
3. `event_type`
4. `payload_version`
5. `collected_at`

사이트 종속 필드는 `payload.data` 아래로 넣어 스키마 충돌을 줄인다.

---

## 6) Execution & Orchestration

운영에서는 Prefect(또는 동급 orchestrator)를 사용하고, 로컬에서는 `jobs/*.py`를 직접 실행 가능하게 유지한다.

권장 원칙:

1. Flow는 orchestration만 담당
2. 비즈니스 로직은 `sites/*`와 `jobs/*`에서 처리
3. 동일 로직이 standalone/script/flow에 중복되지 않도록 단일 진입 함수 사용

---

## 7) Evolution Plan

### Phase 1 (현재)

1. `deal-hub-platform` v1 구조로 리포 시작
2. 쿠팡 1개 사이트만 먼저 마이그레이션
3. core schema + coupang schema 정착

### Phase 2

1. hotdeal 룰 엔진 고도화
2. outbox 기반 알림 안정화
3. 운영 모니터링/재시도/에러 큐 도입

### Phase 3

1. 리워드/공구 도메인 추가
2. 사이트 추가 시 플러그인 방식으로 확장

---

## 8) Naming Notes

레포명은 `deal-hub-platform`을 사용하고, 내부 패키지는 `deal_hub` 또는 `deal_hub_platform`으로 통일하는 것을 권장한다.
