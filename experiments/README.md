# Agent 비교 실험 — 2026-10-31

## 질문과 조건

같은 통합 과제 “Python 바이트 버퍼 `b'abcdefghij'`에서 인덱스 1부터 길이 3인 구간을 인덱스 6부터 복사해 정확한 결과를 반환하는 함수를 작성하고 테스트”를 별도 Agent 세 개에 주었다. 세 Agent는 같은 모델·노력 설정의 Codex 구현 Agent이며, 실제 서로 다른 사람이나 서로 다른 조직 계정을 뜻하지 않는다.

- `baseline-personal`: 개인 `personal-b` Bank만 조회. 관련 기억 0건.
- `baseline-git`: 승인된 Git `origin/main`의 YAML만 조회.
- `agent-b`: Hindsight `team-compiler`를 검색하고 승인된 Git 원본을 재확인.

세 조건의 접근 가능한 자료는 의도적으로 다르게 지정했고, 출처 확인 방식도 각각의 조건에 맞게 다르다. 제공 프롬프트는 공통 업무를 포함하지만 완전히 동일하지 않다. 토큰 수·걸린 시간은 수집하지 않았고, 조건별 1회 실행이므로 재현성·통계적 우위를 주장할 수 없다.

## 관찰

| 조건 | 개인·팀 지식 조회 결과 | 지정 복사 결과 | 해당 Agent 자체 테스트 |
|---|---|---|---|
| 개인 기억만 | 관련 기억 없음 | `b'abcdefbcdj'` | 1개 통과 |
| 승인된 Git 문서 | `COMP-014`, main `3414c778...` | `b'abcdefbcdj'` | 2개 통과 |
| Hindsight + Git 확인 | `COMP-014`, main `3414c778...` | `b'abcdefbcdj'` | 최초 작업 3개 통과 |

세 실행 모두 주어진 입력에서 정답을 냈다. 이 한 사례는 Hindsight가 Git 직접 조회나 개인 기억보다 더 정확하다는 결론을 뒷받침하지 않는다. 모델이 기본 지식만으로 풀 수 있는 쉬운 예제이기도 하다. 각 Agent가 직접 남긴 `trace.md`와 코드·테스트에서 실제 호출과 결과, 한계를 확인할 수 있다. 테스트 개수가 서로 달라 개수 자체를 성능 지표로 비교하지 않는다.

## 실행

```bash
(cd experiments/baseline-personal && python3 -m unittest -v)
(cd experiments/baseline-git && python3 -m unittest -v)
(cd experiments/agent-b && python3 -m unittest -v)
```

각 Agent는 Python 파일을 별도 작업 공간에 작성했다. 기존 코드 예제나 원본 지식의 사실성과 Agent 작성 코드의 품질을 동일시하지 않는다. 파일 안의 로컬 홈 경로는 공유 가능한 형태로 축약했다.

이후 Hindsight 조건의 Agent B가 길이 0인 복사에 대해 별도 경계조건 테스트 4개를 추가했다. B가 작성한 초기 3개 테스트와 함께 7개가 통과했다. 후속 경계조건 검증은 위의 세 조건 간 최초 작업 비교와 별개다.
