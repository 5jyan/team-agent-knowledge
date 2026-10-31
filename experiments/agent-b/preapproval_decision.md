# COMP-014 사전 승인 판단

실행 시각: `2026-10-31T20:59:14+09:00` 전후

## 판단

**보류한다.** `bytearray(b"abc")`에서 `src=dst=3`, `length=0`인 호출이
현재 예제 구현에서 동작한다는 사실은 확인했지만, 승인된 팀 규칙이 그
zero-length 경계조건을 명시하지 않으므로 팀 기준으로 허용된다고 확정하지
않는다. 지식 갱신 PR이 사람의 승인을 받기 전까지는 이 조건을 개인 검증
결과로만 취급한다.

## 승인된 팀 근거

### Hindsight `team-compiler` 재검색

다음 endpoint에 새로 질의했다.

```text
POST http://127.0.0.1:8888/v1/default/banks/team-compiler/memories/recall
query = "COMP-014: Is copying zero bytes from src=3 to dst=3 in bytearray(b'abc') an approved valid no-op when both indexes equal len(buffer)?"
budget = low
types = [world, experience, observation]
```

실제 응답은 `HTTP 200`, `result_count 7`이었다. 승인 문서 ID가 붙은 결과는
`document_id: COMP-014`였고, 다음 메모리와 원본 metadata를 확인했다.

- memory `cf793506-86be-4eaa-8e2d-5cf8bc714c32`: 유효한 비겹침 범위에서만 순방향 복사를 사용하며, 겹치면 아직 읽지 않은 원본이 덮일 수 있다는 내용.
- memory `4233f753-a008-4901-bcf4-dd105f850c27`: 겹치는 범위에서는 원본 스냅샷 안전 경로를 사용한다는 내용.
- memory `233f0ca1-2511-4bfd-bd8b-d0747a33cb93`: COMP-014의 비겹침 복사·겹침 회귀·안전 경로와 기존 로컬 테스트 6개가 검증되었다는 내용.

위 문서 결과들의 metadata는 공통으로 다음을 가리켰다.

```text
knowledge_id: COMP-014
status: active
source_path: knowledge/COMP-014.yaml
source_repository: 5jyan/team-agent-knowledge
source_snapshot: 3414c778b2c1212f167d99f7ec0c9806408504b0
```

recall 결과에는 `length == 0`, `src == dst == len(buffer)`, 또는 zero-length
no-op을 허용한다는 문장이 없었다. 따라서 Hindsight의 승인 지식만으로는
질문의 호출을 허용한다고 결론 낼 수 없다.

### Canonical Git 원본 재확인

다음 명령을 실행했다.

```text
git show origin/main:knowledge/COMP-014.yaml
git rev-parse origin/main
```

실제 원본은 `revision: r1`, `status: active`이며, 다음 범위만 명시한다.

```text
applies_when:
  - 가상의 bytearray 예제에서 복사 범위가 겹치지 않고 인수가 유효하다.
does_not_apply_when:
  - 범위가 겹치거나 예제 외부의 메모리 모델을 사용한다.
```

`origin/main` commit은
`3414c778b2c1212f167d99f7ec0c9806408504b0`이고, YAML의 `evidence.commit`은
`e8d49afc16b9af0be7b7f05e909f7abf9921fe59`다. `인수가 유효하다`의 정의나
zero-length 경계에 대한 별도 규칙은 승인 YAML에 없다.

## 개인 검증 경험과 분리한 실제 테스트

승인 근거와 별개로 저장소의 현재 예제 구현을 직접 실행했다. 실행 명령은
`team-agent-knowledge`에서 다음 Python snippet이었다.

```text
python3 - <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path('examples/demo-compiler/optimizer.py').resolve()
spec = importlib.util.spec_from_file_location('optimizer_preapproval_check', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

memory = bytearray(b'abc')
plan = module.copy_range(memory, src=3, dst=3, length=0)
print('length=0:', plan, memory)
try:
    module.copy_range(bytearray(b'abc'), src=3, dst=3, length=1)
except Exception as exc:
    print('length=1:', type(exc).__name__, str(exc))
PY
```

실제 출력:

```text
length=0: CopyPlan(knowledge_id='COMP-014', revision='r1', path='nonoverlap-fast') bytearray(b'abc')
length=1: ValueError copy range is outside the toy buffer
```

이 테스트는 현재 코드가 zero-length 호출을 받아들이는 것을 보여주는 개인
검증이다. 승인된 팀 규칙의 추가 증거나 사람의 PR 승인으로 간주하지 않는다.
테스트는 실행했으며 성공했다. 이 판단을 위해 repository 파일, knowledge YAML,
Hindsight memory를 수정하지 않았다.

## 결론과 보류 범위

질문의 호출은 현재 구현상 허용되지만, **승인된 COMP-014 규칙으로 허용해도
된다고 답하지 않는다**. zero-length 조건은 승인 문서에 명시되지 않았으므로
사람의 검토와 지식 갱신 승인이 끝날 때까지 보류한다.

이 파일만 생성했으며 다른 파일은 수정하지 않았다.

검증 종료 시 공유 checkout에서 `git -C team-agent-knowledge status --short --branch`를
확인했을 때 다음 상태가 보였다.

```text
## candidate/comp-014-boundary-evidence...origin/candidate/comp-014-boundary-evidence
 M EVIDENCE.md
 M README.md
 M knowledge/COMP-014.yaml
```

이 세 파일은 이 판단 작업에서 수정하지 않았고, 공유 디스크의 다른 Agent 변경을
되돌리지 않았다.
