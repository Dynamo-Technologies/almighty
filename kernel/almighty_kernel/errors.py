"""Errors raised by the namespaced DAG wrapper."""


class KernelError(Exception):
    """Base class for kernel-level errors."""


class MissingNamespaceError(KernelError):
    """Raised when a commit or read is attempted without a (tenant_id, scenario_id) pair.

    This is the WS-104 contract: every operation against the DAG MUST carry
    both identifiers. Application code that omits either gets this error
    instead of being able to fall through to a default namespace.
    """


class NamespaceMismatchError(KernelError):
    """Raised when an event references a predecessor from a different namespace.

    The PyRapide DAG is partitioned per ``(tenant_id, scenario_id)``. A new
    event whose ``causal_predecessors`` list includes IDs not in the same
    namespace would either silently leak across the boundary or fail in a
    confusing way later. We fail loudly at commit time instead.
    """
