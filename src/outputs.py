from datetime import datetime as dt
import csv
import logging

from prettytable import PrettyTable
from constants import (
    DATETIME_FORMAT, BASE_DIR,
    RESULTS_DIR_PATH, IN_FILE_SAVE, PRETTY_IN_TERMINAL_DISPLAY
)


def control_output(results, cli_args):
    if cli_args.output == PRETTY_IN_TERMINAL_DISPLAY:
        pretty_output(results)
    elif cli_args.output == IN_FILE_SAVE:
        file_output(results, cli_args)
    else:
        default_output(results)


def default_output(results):
    for row in results:
        print(*row)


def file_output(results, cli_args):
    results_dir = BASE_DIR / RESULTS_DIR_PATH
    results_dir.mkdir(exist_ok=True)
    parser_mode = cli_args.mode
    now = dt.now().strftime(DATETIME_FORMAT)
    file_name = f'{parser_mode}_{now}.csv'
    file_path = results_dir / file_name
    with open(file_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(
            f, dialect='unix',
            quoting=csv.QUOTE_NONE, escapechar='\n'
        )
        writer.writerows(results)
    logging.info(f'Файл с результатами был сохранён: {file_path}')


def pretty_output(results):
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)
