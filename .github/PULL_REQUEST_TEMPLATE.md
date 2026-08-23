## Summary

Describe the behavior changed and why.

## Safety and privacy

- [ ] Tests and fixtures are synthetic and contain no secrets or personal data.
- [ ] The change does not weaken documented fail-closed or output-safety rules.
- [ ] New files are covered by the privacy audit and package manifest as needed.

## Verification

- [ ] Unit tests pass.
- [ ] `scripts/privacy_audit.py` passes.
- [ ] `scripts/privacy_audit.py --self-test` passes.
- [ ] Relevant macOS, Windows, and Linux behavior is documented or tested.
