# Agent B 실행 trace

실행 시각: `2026-10-31T20:55:16+09:00` 전후

## 팀 지식과 원본 확인

### Hindsight recall

다음 질의를 직접 실행했다.

```text
POST http://127.0.0.1:8888/v1/default/banks/team-compiler/memories/recall
query = "COMP-014: for bytearray b'abcdefghij', copy the range starting at index 1 with length 3 into the destination starting at index 6; what safety condition and copy behavior apply?"
budget = "low"
types = ["world", "experience", "observation"]
```

실제 결과는 `HTTP 200`, `results 7`이었다. 적용 조건을 담은 관찰 메모리의 ID는
`874078a3-31ba-4929-bb83-dec0c57a732f`이며, 다음 내용을 반환했다.

> 가상의 bytearray 예제에서는 인수가 유효하고 원본과 대상 버퍼 범위가 겹치지 않을 때만 순방향 복사를 사용해야 한다. 범위가 겹치면 아직 읽지 않은 원본 바이트가 덮어써질 수 있으므로 원본 스냅샷을 사용하는 안전한 경로를 사용해야 한다.

문서 ID가 명시된 실제 world 결과는 `COMP-014`였다. 메모리 ID
`cf793506-86be-4eaa-8e2d-5cf8bc714c32`의 metadata는 다음과 같았다.

```text
managed_by: team-agent-knowledge
source_repository: 5jyan/team-agent-knowledge
source_path: knowledge/COMP-014.yaml
source_snapshot: 3414c778b2c1212f167d99f7ec0c9806408504b0
knowledge_id: COMP-014
status: active
knowledge_sha256: b990ed7c316517d15841bd78e3179d0e903134e9c5d42d1619d2088c0c047c1b
```

같은 recall에서 `233f0ca1-2511-4bfd-bd8b-d0747a33cb93`도 문서 ID
`COMP-014`로 반환되었고, 비겹침 복사·겹침 회귀·안전 경로와 로컬 테스트 6개가
검증되었다는 기록을 확인했다.

### Canonical Git 원본

로컬 checkout `<WORKSPACE>/team-agent-knowledge`에서 다음을 실행했다.

```text
git fetch origin main
git rev-parse origin/main
git show -s --format='%h %H %s' origin/main
```

실제 최신 원격 결과는 다음과 같다.

```text
3414c778b2c1212f167d99f7ec0c9806408504b0
3414c77 3414c778b2c1212f167d99f7ec0c9806408504b0 Merge pull request #1 from 5jyan/candidate/comp-014-buffer-copy
```

`origin/main:knowledge/COMP-014.yaml`의 현재 원본을 직접 읽어 `status: active`,
`revision: r1`, 적용 조건이 유효한 비겹침 bytearray 범위임을 확인했다. 해당 YAML의
`evidence.commit`은 `e8d49afc16b9af0be7b7f05e909f7abf9921fe59`이며, Hindsight가
가리킨 최신 snapshot은 병합된 `3414c778...`이다. Hindsight의 `knowledge_sha256`는
게시기가 YAML 파일 바이트가 아니라 정규화된 지식 record에 계산한 값이므로 raw
파일의 SHA-256과 혼동하지 않는다.

## 구현과 검증

소유 폴더에 다음 파일만 만들었다.

- `buffer_copy.py`: `copy_range(buffer, src, dst, length) -> bytes` 통합 함수
- `test_buffer_copy.py`: 지정 예제, 양방향 겹침 안전 경로, 잘못된 범위 테스트

비겹침이면 순방향 복사를 수행하고, 겹치면 쓰기 전에 source slice를 스냅샷한다.
입력은 변경하지 않으며 반환 형식은 항상 `bytes`다. 지정 입력은
`b"abcdefghij"`, `src=1`, `dst=6`, `length=3`이고 결과는
`b"abcdefbcdj"`이다.

실제로 실행한 명령과 결과:

```text
$ python3 -m unittest -v test_buffer_copy
Ran 3 tests in 0.000s
OK

$ python3 buffer_copy.py
b'abcdefbcdj'

$ python3 -m py_compile buffer_copy.py test_buffer_copy.py
exit status 0

$ python3 work/agent-b/test_buffer_copy.py
Ran 3 tests in 0.000s
OK

$ python3 - <<'PY' ... PY
exhaustive snapshot-equivalence: sizes 1..8, all valid src/dst/length combinations passed
```

실패한 검증은 없다.

## 범위와 한계

- 이 구현은 지식 문서가 적용되는 Python `bytes`/`bytearray` 장난감 버퍼 범위만 다룬다.
- 겹치지 않는 구간에서 순방향 경로를 사용하고, 겹치는 구간은 원본 스냅샷으로 보존한다.
- 음수·범위 초과·잘못된 타입은 예외로 거절한다.
- 실제 컴파일러, 다른 런타임·메모리 모델, 성능 특성까지 보장하는 증거는 없다.
- Hindsight recall과 canonical Git 원본은 확인했지만, 이 작업은 외부 저장소나 팀 지식 문서를 수정하지 않았다.

## 추가 경계조건 점검: zero-length 복사

점검 시각: `2026-10-31` 후속 실행

이번 점검은 기존 회귀가 새로 발견됐다는 주장이 아니다. B가 승인된
`COMP-014`의 명시되지 않은 경계조건을 별도로 확인한 결과다.

### 실행 경로

추가 테스트 파일은 `work/agent-b/test_zero_length_boundary.py`다. 이 파일은
현재 함수 `work/agent-b/buffer_copy.py`를 import하고, 저장소 코드를 수정하지
않은 채 다음 원본을 `importlib`로 직접 로드한다.

```text
team-agent-knowledge/examples/demo-compiler/optimizer.py
```

따라서 나중에 테스트를 저장소로 옮길 때 필요한 의존 경로는
`examples/demo-compiler/optimizer.py`이며, 현재 실행 명령은 다음과 같다.

```text
cd work/agent-b
python3 -m unittest -v test_zero_length_boundary.py
```

실제 결과:

```text
Ran 4 tests in 0.000s
OK
```

저장소 루트에서의 이식 확인도 실행했다.

```text
python3 work/agent-b/test_zero_length_boundary.py
```

실제 결과 역시 `Ran 4 tests in 0.000s` 및 `OK`였다. 첫 비교용 일회성
스크립트는 `work/agent-b`에 `__init__.py`가 없어 `from work.agent_b ...`가
실패하며 `ModuleNotFoundError: No module named 'work.agent_b'`를 냈다. 테스트
파일의 실제 경로를 `sys.path`에 넣도록 고쳐 같은 비교를 재실행했고, 아래 결과를
얻었다. 저장소 코드나 테스트는 수정하지 않았다.

### 실제 양쪽 동작

버퍼 길이가 3인 `abc`에서 `src=dst=len(buffer)=3`을 실행했다.

```text
repository length=0 src=dst=len=3 -> CopyPlan(knowledge_id='COMP-014', revision='r1', path='nonoverlap-fast') memory= bytearray(b'abc') same_input= True
repository length=1 src=dst=len=3 -> ValueError copy range is outside the toy buffer
integrated length=0 src=dst=len=3 -> b'abc' memory= b'abc' same_input= True
integrated length=1 src=dst=len=3 -> ValueError copy range is outside the buffer
```

두 구현 모두 `length=0`에서는 끝 위치를 유효하게 받아 원본을 보존했고,
`length=1`에서는 같은 시작점이 범위를 벗어나므로 거절했다. 차이는 API 계약이다.
저장소 `optimizer.copy_range`는 `bytearray`를 직접 변경하고 `CopyPlan`을 반환하며,
현재 통합 함수는 `bytes` 또는 `bytearray`를 받아 새 `bytes`를 반환한다. 오류 문구도
각 구현에 맞게 다르다. zero-length 유효성 자체의 결과는 양쪽이 같았다.

### 승인 지식에서 확인한 미명시 부분과 갱신 후보

현재 `knowledge/COMP-014.yaml`의 `r1`에는 비겹침 순방향 복사와 겹침 시
스냅샷 규칙은 있지만 `length == 0`의 유효 범위가 별도로 적혀 있지 않다.
`optimizer.py`의 `_overlaps`는 `length > 0`일 때만 겹침으로 판정하고,
`_validate`는 길이 0일 때 `src`와 `dst`가 `len(buffer)`인 경우를 허용한다.

팀 지식 갱신 후보로 제안할 정확한 추가 조건은 다음 한 문장이다.

> `length == 0`이고 `0 <= src <= len(buffer)`, `0 <= dst <= len(buffer)`이면 빈 복사를 유효한 no-op으로 허용해 버퍼를 변경하지 않는다. `length > 0`이면 `src + length <= len(buffer)` 및 `dst + length <= len(buffer)`가 필요하므로 `src == dst == len(buffer)`는 범위 초과로 거절한다.

이번 결과는 이 후보 조건이 현재 저장소 예제와 B의 통합 함수 양쪽에서 실제로
관찰된다는 근거이며, `COMP-014` 원본 YAML이나 Hindsight 문서를 갱신했다는
의미는 아니다.

추가로 원본 저장소의 기존 회귀 모음도 다시 실행했다.

```text
cd team-agent-knowledge
python3 -m unittest discover -s examples/demo-compiler -p 'test_*.py' -v
Ran 6 tests in 0.002s
OK
```

원본 저장소 `git status --short --branch`는 `## main...origin/main`으로 변경
없음을 확인했다.

현재 B 폴더의 두 테스트 모음을 함께 실행한 결과도 기록한다.

```text
cd work/agent-b
python3 -m unittest -v test_buffer_copy.py test_zero_length_boundary.py
Ran 7 tests in 0.000s
OK
python3 -m py_compile buffer_copy.py test_buffer_copy.py test_zero_length_boundary.py
exit status 0
```

공유용 사본 메모: 홈 경로를 `<WORKSPACE>`로 축약했고, 경계 테스트 파일의 repository 경로를 이 저장소 안에서 재실행되도록 조정했다. 원래 실행 시점의 기록은 위와 같다.
