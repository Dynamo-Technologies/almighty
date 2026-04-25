# `almighty-czml-validator` — WS-202

> **Classification:** UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY

Capability-gated validator for proposed CZML packets. Closes the gate
between officer tools (WS-402) emitting effects and the live CZML adapter
(WS-503) publishing them: every spatial artifact is checked against the
issuing entity's capability profile (WS-106 / WS-107) and the static
capability constraints declared on the CZML template (WS-201).

## What this validates

Per the runbook prompt for WS-202:

1. The post-substitution CZML packet's `template_id` resolves to a real
   template under [`czml/templates/`](../../czml/templates/).
2. The supplied capability profile authorizes the effect family the
   template emits — i.e., the profile's `action_verbs_available` contains
   at least one verb that emits this family per
   [WS-108 § 6](../../docs/schema/artifacts.md#6-verb--artifact-emission-table),
   AND the family appears in `effect_parameter_ranges`.
3. Every parameter declared in the template's `capability_constraints`
   is present in the substitution payload AND falls inside
   `intersect(template.capability_constraints, profile.effect_parameter_ranges[family])`.

The validator rejects on the **first** violating reason and returns it as
a single-element `reasons` list. That keeps the contract simple and lets
the caller surface a precise message in EXCON consoles / AAR.

## API contract

The validator exposes both a Python library and a FastAPI HTTP service.

### Library (in-process)

```python
from almighty_czml_validator import Validator, ValidateRequest

v = Validator()  # reads templates from czml/templates/ at repo root
result = v.validate(ValidateRequest(
    template_id="indirect-fire-arc",
    template_version=1,
    params={
        "range_m": 10000,
        "time_of_flight_s": 25,
        "dispersion_ellipse_a_m": 50,
        "dispersion_ellipse_b_m": 50,
    },
    agent_id="blue-bn-s3",
    capability_profile=us_bct_profile_dict,
))
assert result.accepted
```

A bare `validate(...)` convenience function exists for callers that don't
want to instantiate a `Validator`.

### HTTP (FastAPI)

```
POST /validate
Content-Type: application/json

{
  "template_id":      "indirect-fire-arc",
  "template_version": 1,
  "params":           { "range_m": 10000, ... },
  "agent_id":         "blue-bn-s3",
  "capability_profile": { ... full profile JSON ... }
}
```

Response:

```json
{ "accepted": true,  "reasons": [] }
{ "accepted": false, "reasons": ["'radius_m'=99999 out of range [100, 8000] (intersect(template[jamming-circle], profile[jamming_circle]))"] }
```

`GET /healthz` returns `{ "status": "ok" }`.

## Run

```bash
# From this directory (services/czml-validator/):
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"

# Run the HTTP service:
uvicorn almighty_czml_validator.app:app --reload --port 8011

# Run the test suite:
pytest -v
```

The FastAPI service finds templates via the package's repo-relative
default (`czml/templates/`). To override (e.g. for a deployment that
ships templates in a different path), construct your own `Validator(
template_loader=TemplateLoader(templates_dir=...))` and wire it into a
custom `app`.

## Tests

The suite is parameterized over the four WS-107 profiles
(`us-bct`, `peer`, `near-peer`, `hybrid-irregular`). For each
`(profile, family)` pair where the profile authorizes the family, two
tests run:

- **`test_accept_midpoint`** — builds a packet with each constrained
  param at the midpoint of `intersect(template, profile)`. Must accept.
- **`test_reject_out_of_range`** — pushes one constrained param past the
  intersect upper bound. Must reject, with the violating param name in
  the reason string.

Plus four standalone reject-path tests:

- Profile is missing the emitting verb (US BCT cannot emit
  `jamming_circle` — has no `jam`).
- Profile is missing the family from `effect_parameter_ranges`.
- Template id is unknown.
- A required constrained param is absent from the substitution payload.

Plus three HTTP-layer smoke tests against the FastAPI app
(`/healthz`, accept path, reject path).

Profiles are loaded fresh from
[`kernel/capability-profiles/`](../../kernel/capability-profiles/) at
session start; templates from
[`czml/templates/`](../../czml/templates/). When either upstream changes,
re-run the suite — no test fixtures duplicate authoritative data.

## Layout

```
services/czml-validator/
├── pyproject.toml
├── README.md                      ← this file
├── src/almighty_czml_validator/
│   ├── __init__.py                ← public exports
│   ├── app.py                     ← FastAPI app
│   ├── families.py                ← template_id ↔ family mapping; verb-emission table
│   ├── models.py                  ← ValidateRequest, ValidationResult (Pydantic)
│   ├── templates.py               ← TemplateLoader (repo-relative)
│   └── validator.py               ← Validator core; bare `validate(...)`
└── tests/
    ├── conftest.py                ← fixtures: validator, profiles, template loader
    ├── test_app.py                ← HTTP layer
    └── test_validator.py          ← parameterized + standalone
```

## Notes

- **First-violation reject is the contract.** If you need an exhaustive
  list of every violation in a packet, that's a v2 feature. Do not file
  a bug if the validator returns one reason when there are several
  out-of-range params; that's by design.
- **Profile ownership and clamping.** WS-106 § 6 (uncertainty bands)
  prescribes that red-side validation clamps to the upper bound of the
  uncertainty band before the family-range check. v1's validator does
  NOT yet implement uncertainty clamping — that is a follow-up tracked
  for the kernel side once an uncertainty consumer (WS-404) lands. For
  v1, agents are expected to issue values inside the profile's posted
  range.
- **Cross-tenant safety.** The validator is stateless and tenant-agnostic
  — every call carries its own profile. It cannot leak across tenants
  because it has no shared state to leak. The HTTP service does NOT
  currently enforce tenant scoping on the inbound JWT; that is layered
  on by the call site (in-process tools attach tenant context per
  WS-104).

## See also

- [`docs/schema/artifacts.md`](../../docs/schema/artifacts.md) — verb→artifact mapping (WS-108).
- [`docs/schema/capability-profiles.md`](../../docs/schema/capability-profiles.md) — profile schema (WS-106).
- [`czml/templates/README.md`](../../czml/templates/README.md) — template format (WS-201).
- WS-402 (#22) — primary in-process consumer (officer tool wrappers).
- WS-503 (#28) — primary HTTP consumer (live CZML adapter).
