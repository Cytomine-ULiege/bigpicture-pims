# * Copyright (c) 2020. Authors: see NOTICE file.
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *      http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.

from typing import Union, Optional

import numpy as np

from pydantic.color import Color as PydanticColor, ColorType as PydanticColorType, ColorError, RGBA, parse_tuple, \
    parse_str, ints_to_rgba, float_to_255

ColorType = Union[PydanticColorType, int]


class Color(PydanticColor):
    def __init__(self, value: ColorType) -> None:
        self._rgba: RGBA
        self._original: ColorType
        if isinstance(value, (tuple, list)):
            self._rgba = parse_tuple(value)
        elif isinstance(value, int):
            self._rgba = parse_int(value)
        elif isinstance(value, str):
            self._rgba = parse_str(value)
        elif isinstance(value, Color):
            self._rgba = value._rgba
            value = value._original
        else:
            raise ColorError(reason='value must be a tuple, list, int or string')

        # if we've got here value must be a valid color
        self._original = value

    def as_float_tuple(self, alpha: Optional[bool] = None) -> tuple:
        """
        Return color as a tuple of float in [0, 1].

        Parameters
        ----------
        alpha
            Whether to include the alpha channel, options are
              None - (default) include alpha only if it's set (e.g. not None)
              True - always include alpha,
              False - always omit alpha,
        """
        r, g, b = self._rgba[:3]
        if alpha is None:
            if self._rgba.alpha is None:
                return r, g, b
            else:
                return r, g, b, self._alpha_float()
        elif alpha:
            return r, g, b, self._alpha_float()
        else:
            # alpha is False
            return r, g, b

    def as_int(self, alpha: Optional[bool] = None) -> int:
        """
        Return color as an integer.

        Parameters
        ----------
        alpha
            Whether to include the alpha channel, options are
              None - (default) include alpha only if it's set (e.g. not None)
              True - always include alpha,
              False - always omit alpha
        """
        r, g, b = [float_to_255(c) for c in self._rgba[:3]]

        if alpha is None:
            if self._rgba.alpha is None:
                a = 0
            else:
                a = float_to_255(self._rgba[3])
        elif alpha:
            a = float_to_255(self._rgba[3])
        else:
            a = 0

        return (r & 255) << 24 | (g & 255) << 16 | (b & 255) << 8 | (a & 255) << 0

    def is_grayscale(self) -> bool:
        r, g, b = self._rgba[:3]
        return r == g == b

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Color) and o.as_rgb_tuple() == self.as_rgb_tuple()


def parse_int(value: int) -> RGBA:
    """
    Convert a 32-bit int color to a 8-bit RGBA quadruplet.

    Parameters
    ----------
    value : int
        Integer value to convert

    Returns
    -------
    rgba : RGBA
        Color representation as a RGBA quadruplet.
    """
    r = value >> 24 & 255
    g = value >> 16 & 255
    b = value >> 8 & 255
    a = (value >> 0 & 255) / 255

    return ints_to_rgba(r, g, b, a)


def np_int2rgb(color_int, alpha: bool = False):
    """
    Convert a 32-bit int color to a 8-bit RGB triplet.

    Parameters
    ----------
    color_int : array-like
        Integer values to convert
    alpha : boolean
        Whether to include the alpha channel, options are
          True - always include alpha,
          False - always omit alpha,

    Returns
    -------
    rgb : array-like
        Color representation as a RGB triplet.
        Output shape is `color_int.shape + (3,)` if alpha is omitted,
        `color_int.shape + (4,)` otherwise.
    """
    r = color_int >> 24 & 255
    g = color_int >> 16 & 255
    b = color_int >> 8 & 255
    stack = (r, g, b)

    if alpha:
        a = (color_int >> 0 & 255) / 255
        stack += (a,)

    return np.squeeze(np.dstack(stack))


WHITE = Color((255, 255, 255))
RED = Color((255, 0, 0))
GREEN = Color((0, 255, 0))
BLUE = Color((0, 0, 255))
RGB = [RED, GREEN, BLUE]


def is_rgb(colors):
    if len(colors) != 3:
        return False

    for c1, c2 in zip(RGB, colors):
        if c1 != c2:
            return False
    return True