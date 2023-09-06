from bs4 import BeautifulSoup

from exceptions import ParserFindTagException, InvalidResponseException


def make_soup(session, url, features='lxml'):
    response = get_response(session, url)
    if response is None:
        raise InvalidResponseException(
            'Invalid response received.'
        )
    soup = BeautifulSoup(response.text, features='lxml')
    return soup


def get_response(session, url, encoding='utf-8'):
    response = session.get(url)
    response.encoding = encoding
    return response


def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        raise ParserFindTagException(error_msg)
    return searched_tag
