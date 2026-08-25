class ValidationError(Exception):
    """Erro de validação de negócio, com mensagem segura para exibir ao usuário."""

    def __init__(self, mensagem: str, status_code: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status_code = status_code
