"""Errors raised by the agent runtime."""


class RuntimeError_(Exception):
    """Base class."""


class RuntimeConfigError(RuntimeError_):
    """Required configuration missing or invalid."""


class NamespaceMismatchError(RuntimeError_):
    """A task was picked up by a worker whose tenant_id does not match the
    job's tenant_id. The Celery queue routing should make this impossible
    in practice; raising loudly here is defense in depth.
    """
