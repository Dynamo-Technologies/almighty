"""Almighty kernel — tenant/scenario-namespaced DAG.

Public API is intentionally narrow:

- ``KernelEvent`` — pydantic model mirroring the WS-101 event schema.
- ``NamespacedDag`` — wrapper around PyRapide's Poset that enforces
  ``(tenant_id, scenario_id)`` namespacing on every commit and read.
- ``MissingNamespaceError`` / ``NamespaceMismatchError`` — raised on contract
  violations.
"""

from almighty_kernel.dag import KernelEvent, NamespacedDag
from almighty_kernel.errors import MissingNamespaceError, NamespaceMismatchError

__all__ = [
    "KernelEvent",
    "NamespacedDag",
    "MissingNamespaceError",
    "NamespaceMismatchError",
]
