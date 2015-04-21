import re

from library.helpers.constants import ROWS_96, NUM_COLS_96
from library.helpers.well_naming import get_well_name

BACKWARDS_ROWS = 'BDFH'


def well_to_tile(well):
    '''
    Convert a well (e.g. 'B05') to a tile (e.g. 'Tile000020.bmp').

    '''
    index = well_to_index(well)
    return index_to_tile(index)


def tile_to_well(tile):
    '''
    Convert a tile (e.g. 'Tile000020.bmp') to a well (e.g. 'B05').

    '''
    index = tile_to_index(tile)
    return index_to_well(index)


def well_to_index(well):
    '''
    Convert a well (e.g. 'B05') to a 0-indexed 'snake' position in the plate
    (e.g. 19).

    '''
    if not re.match('[A-H]\d\d?', well):
        raise ValueError('Improper well string')
    row = well[0]
    column = int(well[1:])
    position_from_left = column - 1
    assert position_from_left >= 0 and position_from_left < NUM_COLS_96

    min_row_index = (ord(row) - 65) * NUM_COLS_96
    if row in BACKWARDS_ROWS:
        index_in_row = NUM_COLS_96 - 1 - position_from_left
    else:
        index_in_row = position_from_left

    overall_index = min_row_index + index_in_row
    return overall_index


def index_to_well(index):
    '''
    Convert a 0-indexed 'snake' position in the plate (e.g. 19)
    to a well (e.g. 'B05')

    '''
    row = ROWS_96[index / NUM_COLS_96]
    index_in_row = index % NUM_COLS_96

    if row in BACKWARDS_ROWS:
        position_from_left = NUM_COLS_96 - 1 - index_in_row
    else:
        position_from_left = index_in_row

    column = position_from_left + 1
    return get_well_name(row, column)


def tile_to_index(tile):
    '''
    Convert a tile (e.g. 'Tile000020.bmp') to a 0-indexed 'snake' position
    in the plate (e.g. 19)

    '''
    if not re.match('Tile0000\d\d.bmp', tile):
        raise ValueError('Improper tile string')
    index = int(tile[8:10]) - 1
    return index


def index_to_tile(index):
    '''
    Convert a 0-indexed 'snake' position in the plate (e.g. 19)
    to a tile (e.g. 'Tile000020.bmp').

    '''
    return 'Tile0000{}.bmp'.format(str(index + 1).zfill(2))


if __name__ == '__main__':
    tests = (
        ('A01', 'Tile000001.bmp'),
        ('A12', 'Tile000012.bmp'),
        ('B12', 'Tile000013.bmp'),
        ('B01', 'Tile000024.bmp'),
        ('C02', 'Tile000026.bmp'),
        ('H12', 'Tile000085.bmp'),
        ('H01', 'Tile000096.bmp'),
    )

    for test in tests:
        if well_to_tile(test[0]) != test[1]:
            print 'fail:' + well_to_tile(test[0])
        if tile_to_well(test[1]) != test[0]:
            print 'FAIL: ' + tile_to_well(test[1])
