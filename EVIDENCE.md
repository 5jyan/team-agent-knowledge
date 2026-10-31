# 실행 및 검증 기록

이 문서는 관찰한 결과와 미확인 항목을 구분한다. 추가 검증을 할 때마다 명령·시각·실제 결과를 기록한다.

## 실제 로컬 Hindsight API 스모크 테스트

- 대상: 이 Mac의 Hindsight API `127.0.0.1:8888`, 버전 1.1.0. 모델은 기존 Codex 로그인 계정으로 인증했다.
- 임시 Bank와 가상의 `SMOKE-001` 문서를 사용했다. 초기 내용을 동기 retain한 후 문서를 조회하고 recall했다.
- 동일한 `document_id`로 내용을 replace한 뒤 문서 조회와 recall에서 새 문구가 반환됐다.
- 해당 문서를 삭제한 뒤 문서 목록이 비어 있는 것을 확인하고, 임시 Bank를 삭제했다.
- 이 단일 스모크 테스트는 개인 Bank 접근 권한, 독립 리뷰, 이미 열린 Agent 세션의 기억 갱신, 대규모 검색 정확성을 증명하지 않는다. 실제 교체 중에는 인덱스가 일시적으로 달라질 수 있다.

## 재현용 코드 테스트

`python3 -m unittest discover -s examples/demo-compiler -p 'test_*.py' -v`를 로컬에서 실행해 6개 테스트가 통과했다. r1의 겹치는 버퍼 회귀와 r2의 안전한 결과를 검증한다. 이 테스트의 A/B 표기는 Python 시뮬레이션이며 실제 AI Agent 실행은 아니다.

## 초기 시점의 미확인 항목

- 실제 사람의 후보 PR 근거 검토와 병합, 이후 Publisher 게시.
- Claude Code에 Skill을 로드해 후보 PR을 만드는 실제 Agent 세션.
- B Agent의 업무 수행과, 기존 대화·개인 기억에 남은 옛 지식이 갱신 후 재사용되지 않는지 확인.
- 개인 기억만 사용 / Git 원본 직접 제공 / Hindsight 사용 조건의 동일 작업 비교.
- 서버 측 Bank별 ACL 및 Publisher 전용 쓰기 권한. 로컬 Bank 이름 분리는 권한 격리가 아니다.

위 목록은 초기 기록 당시의 상태이며, 이후 확인한 항목은 아래에 별도 기록한다.

## 후보 PR 생성 후 추가로 확인한 결과

- 로컬 Hindsight에 `personal-a`, `personal-b`, `team-compiler`를 생성했다. 가상의 미확정 가설 `DEMO-UNVERIFIED`를 `personal-a`에 동기 retain한 뒤 같은 질의로 검색했을 때 A에서는 문서 1건, B와 팀 Bank에서는 0건이 반환됐다. 이것은 정상 Bank 라우팅 확인이며 직접 Bank를 지정한 접근에 대한 ACL 테스트가 아니다.
- `COMP-014` 후보 PR을 만들기 전에 `team-compiler`의 문서가 0개인 것을 확인했다. 후보 PR은 병합 또는 게시하지 않았다.
- 구현한 `HindsightClient`로 임시 Bank에 테스트 문서 `COMP-999`를 생성하고 같은 ID로 교체했을 때 문서는 1개였다. 문서를 지우고 0개임을 확인한 뒤 임시 Bank를 삭제했다. 실제 PR 병합부터 Publisher 전체 reconcile까지의 검증은 아니다.
- 초기 `main` 커밋 `e8d49afc16b9af0be7b7f05e909f7abf9921fe59`의 [GitHub Actions 실행](https://github.com/5jyan/team-agent-knowledge/actions/runs/41197913546)이 성공했다. 형식 검사, 저장소 단위 테스트 20개, 모형 테스트 6개를 실행했다. 후보 PR의 CI는 해당 PR에서 별도 확인한다.
- 실제 비공개 GitHub 저장소를 대상으로 `python scripts/validate.py knowledge --verify-remote`를 실행해 후보가 가리키는 커밋을 가져올 수 있음을 확인했다. 이는 링크된 CI 결과와 주장의 적절성에 대한 사람의 검토를 대체하지 않는다.

## 이후 실제 게시 및 Agent 검증

- 사용자가 PR #1을 병합한 main `3414c778b2c1212f167d99f7ec0c9806408504b0`에서 로컬 Publisher를 수동 실행했다. `team-compiler` Bank에 `COMP-014`가 생성됐고 recall에서 범위와 `document_id`를 확인했다. 자동 게시는 구현하지 않았다.
- 별도 Codex Agent B가 Hindsight 팀 Bank를 검색하고 문서 ID 및 승인된 Git 원본을 확인한 후 통합 코드와 테스트를 작성했다. 주어진 복사 사례는 통과했다. 이어서 B가 길이 0의 경계조건을 추가로 점검했다. 실험 로그와 재실행 코드는 [experiments](experiments/README.md)에 있다.
- 개인 기억만 사용한 조건과 승인 Git 문서만 사용한 조건에서도 같은 작업을 각각 1회 수행해 정답을 얻었다. 이 표본만으로 Hindsight의 정확도 우위를 주장할 수 없다.
- 이 갱신 PR을 승인하기 전 팀 Bank 문서를 다시 조회했을 때 `revision: r1`이었고, 제안된 `revision: r2`는 아직 포함되지 않았다. 새 r2의 승인·게시 및 기존 Agent의 게시 후 재확인은 별도 단계다.
- 실제 Claude Code 인증 세션에서 Skill을 실행한 결과, 서버 측 Bank별 ACL, 독립된 제3자 승인 및 후속 갱신의 게시 후 동작은 여전히 확인하지 못했다.
