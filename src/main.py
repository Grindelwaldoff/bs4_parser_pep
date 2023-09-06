import re
from urllib.parse import urljoin
import logging

import requests_cache
from tqdm import tqdm

from constants import BASE_DIR, MAIN_DOC_URL, PEP_DOC_URL, EXPECTED_STATUS
from configs import configure_argument_parser, configure_logging
from outputs import control_output
from exceptions import (
    EmptyTagList, ParserFindTagException,
    InvalidResponseException
)
from utils import find_tag, make_soup


def whats_new(session):
    # Вместо константы WHATS_NEW_URL, используйте переменную whats_new_url.
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    soup = make_soup(session, whats_new_url)

    # Шаг 1-й: поиск в "супе" тега section с нужным id. Парсеру нужен только
    # первый элемент, поэтому используется метод find().
    # Шаг 2-й: поиск внутри main_div следующего тега div с классом
    # toctree-wrapper.
    # Здесь тоже нужен только первый элемент, используется метод find().
    div_with_ul = find_tag(
        soup,
        'div',
        attrs={'class': 'toctree-wrapper'}
    )

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
        soup = make_soup(session, version_link)
        main_page_section = find_tag(
            soup,
            'div',
            attrs={'class': 'body'}
        )  # Найдите в "супе" тег h1.
        dl_text = main_page_section.dl.text.replace('\n', ' ')
        results.append(
            (version_link, main_page_section.h1.text, dl_text)
        )
    return results


def latest_versions(session):
    soup = make_soup(session, MAIN_DOC_URL)
    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    a_tags = sidebar.find_all('a')
    if a_tags == []:
        raise EmptyTagList('Ничего не нашлось')
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    results = [('Link', 'ver.', 'State')]
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

    soup = make_soup(session, downloads_url)

    table_tag = find_tag(soup, 'table', {'class': 'docutils'})

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
        ('Status', 'Amount')
    ]
    statuses = {
        'Active': 0,
        'Deffered': 0,
        'Final': 0,
        'Provisional': 0,
        'Rejected': 0,
        'Superseded': 0,
        'Withdrawn': 0,
        '*Draft/Active': 0,
    }
    soup = make_soup(session, PEP_DOC_URL)
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
        soup = make_soup(session, pep_link)
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
            for keys in statuses.keys():
                if keys.startswith(table_status[1:]):
                    statuses[keys] += 1
                elif table_status[1:] == '':
                    statuses['*Draft/Active'] += 1

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

    try:
        results = MODE_TO_FUNCTION[parser_mode](session)
        if results is not None:
            control_output(results, args)
        logging.info('парсер завершли свою работу')
    except InvalidResponseException:
        logging.exception(
            ('Возникла ошибка при загрузке данных '
             f'со страницы в методе {parser_mode}')
        )
    except ParserFindTagException as error_msg:
        logging.exception(error_msg, stack_info=True)


if __name__ == '__main__':
    main()
