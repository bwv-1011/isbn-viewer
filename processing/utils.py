import math
import hashlib
import numpy as np
from hilbert import decode


def hilbert_rectangle_projection(values: list[int]) -> np.array:
    values = np.array(values)

    mask = values >= 2**30

    values_normed = values % 2**30

    result = decode(values_normed, 2, 15)

    result[mask, 0] += 2**15
    return result


def project_x_y_to_coordinate(x:int, y:int) -> [float, float]:
    lng = x * 360 / (128 * 1000) + (32 / (2**7) * 360 - 180)
    lat = math.degrees(
        math.atan(math.sinh(math.pi * (1 - (2 * (48 + y / 1000)) / (2**7))))
    )
    return lng, lat


def string_to_number(name:str) -> int:
    hash_object = hashlib.sha256(name.encode())
    return int(hash_object.hexdigest(), 16) % (10**9)


def n_prefix_to_zoom_level(n_prefix) -> int:
    translation = {
        1: 2,
        2: 3,
        3: 4,
        4: 6,
        5: 8,
        6: 10,
        7: 11,
    }
    return translation[int(n_prefix)]
