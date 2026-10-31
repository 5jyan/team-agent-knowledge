# Baseline Git trace

## Approved source lookup

조회는 `team-agent-knowledge`의 승인된 Git 원본만 사용했다.

```text
$ git -C team-agent-knowledge rev-parse origin/main
3414c778b2c1212f167d99f7ec0c9806408504b0

$ git -C team-agent-knowledge show -s --format='%H%n%s' origin/main
3414c778b2c1212f167d99f7ec0c9806408504b0
Merge pull request #1 from 5jyan/candidate/comp-014-buffer-copy

$ git -C team-agent-knowledge show origin/main:knowledge/COMP-014.yaml | sed -n '1,45p'
schema_version: 1
type: bugfix
id: COMP-014
status: active
title: "겹치지 않는 버퍼 범위의 순방향 복사"
revision: r1
summary: "가상의 바이트 버퍼에서 원본과 대상 범위가 겹치지 않으면 순방향 복사를 사용할 수 있다."
problem:
  statement: "다른 작업에서 버퍼 복사 경로를 재사용할 때 결과가 보존되는 조건이 필요하다."
cause:
  statement: "원본과 대상 범위가 겹치면 순방향 복사 중 아직 읽지 않은 원본 바이트가 덮일 수 있다."
solution:
  statement: "원본과 대상 범위가 겹치지 않는 경우에만 순방향 복사를 사용한다."
limitations:
  - condition: "입력과 출력의 버퍼 범위가 겹치는 경우"
    action: "순방향 복사 규칙을 적용하지 말고 원본 스냅샷을 사용하는 안전한 경로를 사용한다."
  - condition: "실제 컴파일러, 다른 런타임 또는 다른 메모리 모델"
    action: "이 장난감 예제만으로 동작이나 성능을 보장하지 않는다."
scope:
  applies_when:
    - "가상의 bytearray 예제에서 복사 범위가 겹치지 않고 인수가 유효하다."
  does_not_apply_when:
    - "범위가 겹치거나 예제 외부의 메모리 모델을 사용한다."
evidence:
  repository: "https://github.com/5jyan/team-agent-knowledge"
  commit: "e8d49afc16b9af0be7b7f05e909f7abf9921fe59"
```

출처 ID는 `COMP-014`이다. 적용 근거는 `origin/main` 승인 스냅샷
`3414c778b2c1212f167d99f7ec0c9806408504b0`의 `knowledge/COMP-014.yaml`에
기록된 범위 조건이다. YAML이 인용한 검증 근거 커밋은
`e8d49afc16b9af0be7b7f05e909f7abf9921fe59`이다.

## Decision

`b"abcdefghij"`에서 source index `1`, length `3`인 `b"bcd"`를 destination
index `6`으로 복사하면 결과는 `b"abcdefbcdj"`여야 한다. 승인 문서의 범위
조건에 따라 비겹침 구간은 순방향 복사하고, 겹치는 구간은 원본 스냅샷을
사용하도록 `copy_range`를 구현했다. 인덱스·길이가 음수이거나 범위를 벗어나면
`ValueError`를 반환하는 대신 발생시킨다.

## Validation

```text
$ python3 -m py_compile copy_buffer.py test_copy_buffer.py
# exit 0, no output

$ python3 copy_buffer.py
b'abcdefbcdj'

$ python3 -m unittest -v test_copy_buffer.py
test_overlapping_copy_uses_original_snapshot (test_copy_buffer.CopyRangeIntegrationTest) ... ok
test_requested_non_overlapping_copy (test_copy_buffer.CopyRangeIntegrationTest) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK

$ python3 -m unittest discover -s . -p 'test_*.py' -v
test_overlapping_copy_uses_original_snapshot (test_copy_buffer.CopyRangeIntegrationTest) ... ok
test_requested_non_overlapping_copy (test_copy_buffer.CopyRangeIntegrationTest) ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.000s

OK
```

직접 변경한 파일은 `copy_buffer.py`, `test_copy_buffer.py`, `trace.md`이며,
모든 파일은 이 `work/baseline-git` 폴더 안에 있다.
