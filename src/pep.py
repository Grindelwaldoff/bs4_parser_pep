from urllib.parse import urljoin
import re

import requests_cache
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

from utils import find_tag, get_response
from constants import PEP_DOC_URL, EXPECTED_STATUS



if __name__ == '__main__':
    results = {
        'A': 0,
        'D': 0,
        'F': 0,
        'P': 0,
        'R': 0,
        'S': 0,
        'W': 0,
        '': 0
    }
    session = requests_cache.CachedSession()
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
        if len(table_status) == 2:
            if (
                card_status not in EXPECTED_STATUS[table_status[-1]]
            ):
                mismatched_peps.append((
                    pep_link,
                    card_status,
                    EXPECTED_STATUS[table_status[-1]]
                ))
            else:
                results[table_status[-1]] += 1
        else:
            if card_status not in EXPECTED_STATUS['']:
                mismatched_peps.append(
                    (
                        pep_link,
                        card_status,
                        EXPECTED_STATUS['']
                    )
                )
            else:
                results[''] += 1
    print(results)
    print(mismatched_peps)