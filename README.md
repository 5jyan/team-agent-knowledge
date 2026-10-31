# Team Agent Knowledge

가상의 Compiler 팀에서 한 구성원의 검증된 지식을 다른 구성원의 Agent가 활용하고, 새 반례가 발견되면 지식과 이후의 판단을 갱신하는 프로토타입이다. Git의 지식 YAML이 원본이고 Hindsight는 파생 검색 인덱스다. 실제 컴파일러 제품의 성능에 관한 주장은 하지 않는다.

> 프로젝트와 예제는 비공개로 다룬다. 과제 원문, 회사 코드, 실제 고객 데이터와 비밀키는 저장소에 넣지 않는다.

## 상태

이 저장소에는 가상의 버퍼 복사 예제, 지식 검증과 게시 구성요소가 포함된다. 각 기능의 실행 결과 및 아직 검증하지 못한 단계는 아래와 [DESIGN.md](DESIGN.md)에 구분해 적는다. Agent A/B 대화, 사람의 PR 검토와 병합, 접근 제어 및 후속 갱신은 실제 수행 결과를 확인하기 전까지 성공으로 간주하지 않는다.

## 시나리오

1. A는 입력과 출력이 겹치지 않는 버퍼 복사 예제를 검증하고 `COMP-014` 지식 후보를 작성한다.
2. Agent는 후보 PR을 제안하고, 사용자가 근거와 CI를 검토한 뒤 병합한다. Publisher가 병합된 원본을 Team Bank에 반영한다.
3. B는 팀 지식과 현재 원본의 적용 조건을 확인한 뒤 다른 작업에 활용한다.
4. B가 겹치는 버퍼에서 새 반례를 발견하면 같은 지식의 제한을 수정하는 PR을 제안한다. 이후 Agent는 옛 개인 기억을 갖고 있어도 현재 원본을 확인해야 한다.

모형 코드는 별도 Agent를 호출하지 않는다. 아래 데모의 A/B 표기는 결정적 Python 시뮬레이션이다.

## 빠른 확인

```bash
python3 -m unittest discover -s examples/demo-compiler -p 'test_*.py' -v
python3 examples/demo-compiler/run_demo.py
```

[데모 설명](examples/demo-compiler/README.md)에 실패 재현과 수정의 의미가 있다. 요구 조건과 운영상 한계는 [설계](DESIGN.md), AI 도구와 프롬프트는 [활용 내역](AI_USAGE.md)을 참조한다.

## 설치와 로컬 검증

Python 3.12와 로컬에서 실행 중인 Hindsight API 1.1을 기준으로 한다. Hindsight 설치·LLM 제공자 설정은 [공식 설치 안내](https://hindsight.vectorize.io/developer/installation)를 참고한다. 최초 모델 다운로드 및 LLM 사용에 네트워크 연결이 필요할 수 있다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/validate.py knowledge
python -m unittest discover -s tests -v
python -m unittest discover -s examples/demo-compiler -p 'test_*.py' -v
```

빈 `knowledge/`는 승인 지식이 아직 없는 정상적인 초기 상태다. 검증기의 기본 모드는 형식·필수 항목·기초적인 비밀 패턴을 확인한다. 실제 Git 커밋이 원격 저장소에 존재하는지 별도로 확인하려면 인증된 환경에서 다음을 실행한다.

```bash
python scripts/validate.py knowledge --verify-remote
```

원격 커밋 존재 확인은 CI 실행의 성공이나 주장과 근거의 의미적 일치까지 검증하지 않는다. 그 부분은 사람이 직접 검토한다. 기본 GitHub Actions 검증에도 원격 증거 검증은 포함하지 않는다.

## 승인 후 게시

지식 후보는 `templates/bugfix.yaml`을 참고해 `knowledge/COMP-014.yaml`로 작성하고 PR을 만든다. 사용자가 실제 테스트·근거와 CI를 확인해 병합한 뒤, 자신의 로컬 `main`을 최신 원격 `main`과 일치시킨다. 현재 게시 코드는 원본의 유효성을 확인하지만 GitHub 리뷰 승인이나 Branch Protection이 강제됐는지 증명하지 않는다.

```bash
git switch main
git pull --ff-only origin main
python scripts/validate.py knowledge --verify-remote
python scripts/reconcile.py --snapshot-commit "$(git rev-parse main)" --bank-id team-compiler --dry-run
python scripts/reconcile.py --snapshot-commit "$(git rev-parse main)" --bank-id team-compiler
```

첫 승인 전에는 게시할 지식이 없으므로 Publisher가 빈 snapshot을 거절한다. 기본 API 주소는 `http://127.0.0.1:8888`이고 `--api-url`로 바꿀 수 있다. 이 MVP 클라이언트는 API 인증 헤더를 구현하지 않았으므로 인증이 필요한 서버에 그대로 연결할 수 없다. 로컬 인증 없는 Hindsight는 신뢰할 수 있는 개인 개발 환경에서만 사용한다.

Publisher는 전체 `knowledge/` snapshot을 검증하고 자신이 관리하는 문서만 동기화한다. 로컬 파일 잠금은 같은 checkout 안의 동시 실행만 제한하며, 여러 컴퓨터·별도 checkout의 분산 잠금이나 서버 측 권한 강제는 제공하지 않는다. 게시 실패 후에는 원인과 최신 main 상태를 확인하고 다시 실행한다.

## 실제 결과와 남은 단계

[실행 및 검증 기록](EVIDENCE.md)을 참조한다. Hindsight API의 저장·교체·삭제와 Python 모형 테스트는 로컬에서 확인했다. 실제 승인된 PR, 사용자 리뷰, Claude Agent 간 활용, 갱신 후의 기존 세션 행동 및 대안 비교는 별도 실행 결과가 없으면 완료로 표시하지 않는다.
