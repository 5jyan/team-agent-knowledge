# Python `unittest` discovery example

이 디렉터리는 Python 표준 라이브러리만 사용하는 작은 테스트 실행 예제다.
`tests/` 아래에 테스트 파일을 두되 `tests/__init__.py`는 의도적으로 두지 않는다.
따라서 이 예제 프로젝트 루트에서 기본 실행과 명시적 discovery 실행의 결과를
비교할 수 있다.

## 실행

저장소 루트에서 다음 명령을 실행한다.

```bash
cd examples/unittest-discovery
python3 -m unittest
```

이 예제에서 Python 3.9.6은 `Ran 0 tests`, `OK`, 종료 코드 0을 보였고 Python 3.12.16은 `Ran 0 tests`, `NO TESTS RAN`, 종료 코드 5를 보였다. Python 버전에 따라 종료 결과가 다르므로, 실제 테스트 실행 개수를 확인한다.

`tests/`를 시작점으로 지정해 실제 테스트를 실행하려면 다음 명령을 사용한다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

이 명령은 `tests/test_json_round_trip.py`의 테스트 2개를 실행하고
`Ran 2 tests`를 출력해야 한다. 이 관찰은 이 디렉터리 구조의 예제에만
적용하며, 다른 Python 프로젝트·Python 버전·발견 설정으로 일반화하지 않는다.
