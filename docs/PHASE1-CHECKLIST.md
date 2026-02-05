# Phase 1 Foundation Checklist

## 1) Documentation Integrity

- [ ] All referenced top-level documents exist.
- [ ] Build spec path references are valid (`docs/build/*`).
- [ ] README quick links resolve.

## 2) Stage Gate

- [ ] `pytest -m phase1_ready -q` passes.
- [ ] Stage-gate tests cover docs integrity + minimum DB initialization.

## 3) Quality Gates

- [ ] `black --check src tests ironlung3.py` passes.
- [ ] `isort --check-only src tests ironlung3.py` passes.
- [ ] `mypy src` passes.
- [ ] `pytest -q` passes.

## 4) CI

- [ ] CI runs on push/PR.
- [ ] CI runs Python 3.11.
- [ ] CI executes formatting, import order, typing, stage gate, and full tests.

## 5) Demo/Smoke Readiness

- [ ] Demo seed script can create a local demo DB.
- [ ] Smoke script documents command sequence for fast verification.
