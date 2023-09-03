import re
from urllib.parse import urljoin
import logging

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from constants import BASE_DIR, MAIN_DOC_URL, PEP_DOC_URL, EXPECTED_STATUS
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from utils import find_tag, get_response


def whats_new(session):
    # Вместо константы WHATS_NEW_URL, используйте переменную whats_new_url.
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    # Создание "супа".
    soup = BeautifulSoup(response.text, features='lxml')

    # Шаг 1-й: поиск в "супе" тега section с нужным id. Парсеру нужен только
    # первый элемент, поэтому используется метод find().
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})

    # Шаг 2-й: поиск внутри main_div следующего тега div с классом
    # toctree-wrapper.
    # Здесь тоже нужен только первый элемент, используется метод find().
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})

    # Шаг 3-й: поиск внутри div_with_ul всех элементов списка li с классом
    # toctree-l1.
    # Нужны все теги, поэтому используется метод find_all().
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'}
    )

    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        # Здесь начинается новый код!
        response = get_response(session, version_link)
        if response is None:
            return
        soup = BeautifulSoup(response.text, features='lxml')  # Сварите
        # "супчик".
        h1 = find_tag(soup, 'h1')  # Найдите в "супе" тег h1.
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')  # Найдите в "супе" тег dl.
        results.append(
            (version_link, h1.text, dl_text)
        )
    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    sidebar = find_tag(soup, 'div', class_='sphinxsidebarwrapper')
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    results = []
    for version in a_tags:
        link = urljoin(MAIN_DOC_URL, version['href'])
        text_match = re.search(pattern, version.text)
        if text_match:
            results.append(
                (link, text_match.group('version'),
                 text_match.group('status'))
            )
    return results


def download(session):
    # Вместо константы DOWNLOADS_URL, используйте переменную downloads_url.
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')

    response = get_response(session, downloads_url)
    if response is None:
        return

    soup = BeautifulSoup(response.text, 'lxml')

    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})

    pdf_a4_tag = find_tag(
        table_tag,
        'a',
        {'href': re.compile(r'.+pdf-a4\.zip$')}
    )
    archive_url = urljoin(downloads_url, pdf_a4_tag['href'])
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)

    with open(archive_path, 'wb') as file:
        file.write(response.content)

    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    results = [
        ('Статус', 'Кол-во')
    ]
    statuses = {
        'A': 0,
        'D': 0,
        'F': 0,
        'P': 0,
        'R': 0,
        'S': 0,
        'W': 0,
        '': 0,
    }
    response = get_response(session, PEP_DOC_URL)
    if response is None:
        return
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'lxml')
    index_by_categroy_section = find_tag(
        soup,
        'section',
        attrs={'id': 'index-by-category'}
    )
    numerical_index_section = find_tag(
        soup,
        'section',
        attrs={'id': 'numerical-index'}
    )
    pep_rows = (
        index_by_categroy_section.find_all('td')
        + numerical_index_section.find_all('td')
    )
    mismatched_peps = []
    for pep_data_index in tqdm(range(0, len(pep_rows), 4)):
        # находим статус из таблицы и делаем ссылку на pep
        table_status = pep_rows[pep_data_index].text
        pep_link = urljoin(
            PEP_DOC_URL,
            find_tag(pep_rows[pep_data_index+1], 'a')['href']
        )
        # узнаем статус в карточке
        response = get_response(session, pep_link)
        if response is None:
            return
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'lxml')
        status_sibling_finder = find_tag(soup, 'dl')
        for tag in status_sibling_finder:
            if 'Status' in tag:
                card_status = tag.next_sibling.next_sibling.text
        if (
            card_status not in EXPECTED_STATUS[table_status[1:]]
        ):
            mismatched_peps.append((
                pep_link,
                card_status,
                EXPECTED_STATUS[table_status[1:]]
            ))
        else:
            statuses[table_status[1:]] += 1

    print('Несовпадающие статусы:')
    for pep in mismatched_peps:
        print(
            f'{pep[0]} \n'
            f'Статус в карточке: {pep[1]} \n'
            f'Ожидаемые статусы: {pep[2]}'
        )
    return results + list(
        zip(list(statuses.keys()), list(statuses.values()))
    ) + [['Total', sum(list(statuses.values()))]]


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    configure_logging()
    logging.info('парсер запущен')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'аргументы командной строки: {args}')
    session = requests_cache.CachedSession()

    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode

    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('парсер завершли свою работу')


if __name__ == '__main__':
    main()
