# GH Archive 필드 레퍼런스

`githubarchive.day` 테이블에 무엇이 들어 있고 무엇에 쓸 수 있는지. 조회용 문서.

건수와 크기는 2025-09-24 (전체 3,815,767건) 기준.

---

## 공통 컬럼

모든 이벤트가 갖는 9개. 15년간 변경 없음.

| 컬럼 | 타입 | 내용 | 용도 |
|---|---|---|---|
| `type` | STRING | 이벤트 종류 | 필터링. **값 목록을 상수로 고정하지 말 것** |
| `created_at` | TIMESTAMP | 발생 시각 (UTC) | 모든 시계열 분석의 축 |
| `id` | STRING | 이벤트 고유 ID | 중복 제거 키. 재처리 시 멱등성 보장 |
| `repo` | STRUCT\<id, name, url\> | `name` 은 `owner/repo` | **저장소 추적은 `id` 기준.** 이름은 바뀌어도 id 는 유지 |
| `actor` | STRUCT\<id, login, ...\> | 행위자 | 고유 기여자 수 계산 |
| `org` | STRUCT\<id, login, ...\> | 소속 조직. **개인 저장소는 null** | 조직/개인 저장소 비교 |
| `payload` | STRING (JSON) | 타입별 상세 | 아래 참조 |
| `public` | BOOL | 항상 true | **drop** |
| `other` | STRING | `{"actor":{"display_login":"..."}}` 고정, 42B | **drop** |

`payload` 는 테이블 용량의 대부분이다. 2025-09-24 하루치 스캔이 12.6GB 다. BigQuery 에서 이 컬럼을 건드리는 쿼리는 비용을 먼저 계산해야 한다.

---

## 이벤트 타입별 payload

| 타입 | 하루 건수 | 크기 | 쓸 만한 필드 | 2025-10 이후 |
|---|---|---|---|---|
| **PushEvent** | 2,392,363 | 758B | `ref`, `commits[].message`, `commits[].author`, `size` | `commits`·`size` **삭제**. 179B |
| **CreateEvent** | 450,121 | 131B | `ref`, `ref_type`, `master_branch`, `description` | 유지 |
| **PullRequestEvent** | 283,473 | 19,353B | `pull_request` 의 `title`·`body`·`additions`·`deletions`·`changed_files`·`merged_at`·`labels`·`head.ref`·`author_association` | `head`·`base`·`id`·`number`·`url` 만 남음. 라벨·담당자는 최상위로 이동 |
| IssueCommentEvent | 156,037 | 9,852B | `comment.body`, `issue.pull_request` | 유지 |
| **WatchEvent** | 121,444 | 20B | `action` (항상 `started`) | 유지 |
| DeleteEvent | 96,322 | 83B | `ref`, `ref_type` | 유지 |
| PullRequestReviewEvent | 91,419 | 22,358B | `review.state`, `review.submitted_at` | 51 → 19개 키 |
| **IssuesEvent** | 76,108 | 5,768B | `issue.labels[].name`, `.default`, `.description`, `action` | 유지 |
| PullRequestReviewCommentEvent | 65,748 | 23,849B | `comment.path`, `.line`, `.body` | 66 → 28개 키 |
| **ForkEvent** | 29,816 | 5,503B | 건수 자체 | 유지 |
| **ReleaseEvent** | 19,116 | 4,400B | `release.tag_name`, `.body`, `.prerelease`, `.target_commitish` | 유지 |
| MemberEvent | 13,319 | 993B | `member.login` | 유지 |
| CommitCommentEvent | 3,675 | 4,050B | `comment.body`, `.path` | `action` 추가 |
| GollumEvent | 3,335 | 326B | `pages[].page_name`, `.action` | 유지 |
| PublicEvent | 소수 | 2B | **payload 가 `{}` 빈 객체** | 유지 |
| DiscussionEvent | 없음 | - | 2025-10-22 신규 | 신규 |

굵은 표시는 목표 1·2 에 실제로 쓰는 타입.

---

## 함정

**IssueCommentEvent 의 70.7% 는 실제로 PR 댓글이다.** GitHub 이 PR 을 이슈의 하위 개념으로 다루기 때문이다. 이슈 댓글만 보려면 `issue.pull_request` 키가 **없는** 행으로 걸러야 한다. 모르고 쓰면 이슈 활동을 3배 이상 과대 집계한다.

**CreateEvent 의 `ref` 에는 `refs/heads/` 접두사가 없다.** PushEvent 의 `ref` 는 `refs/heads/xxx` 전체 경로다. 브랜치 명명 분석에 CreateEvent 를 쓰는 실용적 이유다.

**PublicEvent 의 payload 는 빈 객체다.** 파싱 로직에 예외 처리가 필요하다.

**`issue.labels[].default`** 로 GitHub 기본 라벨과 커스텀 라벨을 구분할 수 있다.

**PR 라벨의 경로가 시기에 따라 다르다.** 2025-09 이전 `pull_request.labels`, 이후 `labels`.

---

## 목표별 필요 필드

### 목표 1 — 관례 실태 분석

| 항목 | 필드 | 가용 시기 |
|---|---|---|
| 브랜치 명명 | `CreateEvent.ref` + `ref_type='branch'` | 전 기간 |
| 기본 브랜치 명칭 | `CreateEvent.master_branch` | 전 기간 |
| 릴리스 태그 형식 | `ReleaseEvent.release.tag_name` | 전 기간 |
| 이슈 라벨 | `IssuesEvent.issue.labels[]` | 전 기간 |
| PR 라벨 | `pull_request.labels` → `labels` | 전 기간 (경로 분기) |
| 브랜치 수명 | `CreateEvent` + `DeleteEvent` 의 `ref` | 전 기간 |
| 커밋 메시지 관례 | `PushEvent.commits[].message` | **~2025-09** |
| PR 크기 | `pull_request.additions`·`deletions`·`changed_files` | **~2025-09** |

공통으로 `repo.id`, `created_at`, `org` 가 필요하다.

### 목표 2 — 급증 저장소 생존율

| 단계 | 필드 |
|---|---|
| 급증 탐지 | `type='WatchEvent'`, `repo.id`, `created_at` |
| 보조 지표 | `type='ForkEvent'` |
| 생존 판정 | `type='PushEvent'`, `repo.id`, `created_at` |
| 코호트 보강 | GitHub GraphQL API (404, `isArchived`, `pushedAt`, `stargazerCount`) |

**payload 를 전혀 쓰지 않는다.** 필요한 건 `type`, `repo.id`, `repo.name`, `created_at`, `actor.login` 다섯 개뿐이다.

---

## 실버 테이블 설계 메모

**drop 대상:** `public`, `other`, 모든 `*_url`·`avatar_url`·`gravatar_id`·`node_id`

**공통 컬럼:** `type`, `created_at`, `id`, `repo.id`, `repo.name`, `actor.login`, `org.login`

**목표별 요구가 상반된다.** 목표 2는 컬럼 5개로 전 기간이 필요하고, 목표 1은 컬럼은 많지만 기간이 짧다. 하나의 테이블에 담으면 목표 2가 불필요하게 무거워진다. 분리 여부는 미확정.

**payload 원본 JSON 을 그대로 보관하지 말 것.** 필요한 필드만 컬럼으로 승격한다.

**깊이 3 이상 필드 주의.** 키 조사는 깊이 2까지만 했다. `pull_request.head.ref` 처럼 3단계 필드는 목록에 없지만 존재한다. `../results/rows_*.json` 에서 확인할 것.