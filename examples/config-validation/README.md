# Python config validation demo

This directory is a small, deterministic example of a configuration checker.
It has no external service or dependency beyond Python's standard library.

`config_checker.py` keeps `validate_config_before` as the pre-fix regression
fixture. The corrected `validate_config` reports the missing required `model`
key without echoing configuration values:

```python
if "model" not in config:
    return "설정 오류: model 항목이 없습니다"
return "설정 정상"
```

The demo runs both implementations against the same missing-model input and a
model-present input. The printed input redacts values; the test suite checks the
exact before/after outputs and that an unrelated value is not included in the
error.

Run from the repository root:

```bash
python3 -m unittest discover -s examples/config-validation -p 'test_*.py' -v
python3 examples/config-validation/run_demo.py
```

This example only covers a missing `model` key. It does not validate other
required fields, the contents or type of `model`, or a production application's
configuration policy.
