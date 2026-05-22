class FinDSLError(Exception):
    """Base error for FinDSL Forge."""


class LexError(FinDSLError):
    """Raised when DSL tokenization fails."""


class ParseError(FinDSLError):
    """Raised when DSL parsing fails."""


class SemanticError(FinDSLError):
    """Raised when DSL semantic validation fails."""


class ConfigError(FinDSLError):
    """Raised when compiler configuration is invalid."""

