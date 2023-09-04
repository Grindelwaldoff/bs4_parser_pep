class ParserFindTagException(Exception):
    """Вызывается, когда парсер не может найти тег."""
    pass


class EmptyTagList(Exception):
    """Вызывается, когда find_all не находит элементы."""
    pass
