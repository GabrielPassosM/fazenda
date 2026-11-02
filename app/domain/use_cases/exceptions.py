class DomainError(Exception):
    """Erro de regra de negócio do domínio."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """Recurso não encontrado."""

