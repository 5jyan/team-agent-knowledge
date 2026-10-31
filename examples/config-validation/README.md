# 설정 오류 메시지 예제

설정에 `model`, `version` 키가 필요한 가상 예제다. 기존 방식은 model이 없으면 `설정 오류`만 표시했다. 개선된 방식은 빠진 항목을 모두 표시하고 설정값 자체는 출력하지 않는다.

```bash
python3 examples/config-validation/run_demo.py
python3 -m unittest discover -s examples/config-validation -p 'test_*.py' -v
```

두 항목이 모두 없으면 `설정 오류: model, version 항목이 없습니다`, model만 없으면 `설정 오류: model 항목이 없습니다`다. 두 항목이 있으면 정상이다. 이 예제는 키 존재만 검사하며 값의 타입이나 유효성을 보장하지 않는다.
