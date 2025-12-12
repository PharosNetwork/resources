#!/usr/bin/env python3
# coding=utf-8
"""
    Copyright (C) 2020 Pharos Labs. All rights reserved.

    Desc     : Pharos2.0 Operation Tools
    History  :
    License  : Pharos Labs proprietary/confidential.

    Python Version : 3.6.8
    Created by youxing.zys
    Date: 2022/12/06
"""
from typing import Optional, Any, Sized, Iterable, TypeVar
from marshmallow import validate

_T = TypeVar("_T")

class Range(object):
    """Validator which succeeds if the value passed to it is within the specified
    range. If ``min`` is not specified, or is specified as `None`,
    no lower bound exists. If ``max`` is not specified, or is specified as `None`,
    no upper bound exists. The inclusivity of the bounds (if they exist) is configurable.
    If ``min_inclusive`` is not specified, or is specified as `True`, then
    the ``min`` bound is included in the range. If ``max_inclusive`` is not specified,
    or is specified as `True`, then the ``max`` bound is included in the range.

    :param min: The minimum value (lower bound). If not provided, minimum
        value will not be checked.
    :param max: The maximum value (upper bound). If not provided, maximum
        value will not be checked.
    :param min_inclusive: Whether the `min` bound is included in the range.
    :param max_inclusive: Whether the `max` bound is included in the range.
    :param error: Error message to raise in case of a validation error.
        Can be interpolated with `{input}`, `{min}` and `{max}`.
    """
    _validator: validate.Validator = None

    def __init__(self, min: Optional[int] = None, max: Optional[int] = None):
        self._validator = validate.Range(min, max)

    def __call__(self, value: _T) -> _T:
        return self._validator(value)


class PortType(Range):
    def __init__(self):
        # min 1024 to avoid system port
        Range.__init__(self, 0, 65535)


class Length(object):
    """Validator which succeeds if the value passed to it has a
    length between a minimum and maximum. Uses len(), so it
    can work for strings, lists, or anything with length.

    :param min: The minimum length. If not provided, minimum length
        will not be checked.
    :param max: The maximum length. If not provided, maximum length
        will not be checked.
    """
    _validator: validate.Validator = None

    def __init__(self, min: Optional[int] = None, max: Optional[int] = None):
        self._validator = validate.Length(min, max)

    def __call__(self, value: Sized) -> Sized:
        return self._validator(value)


class NonEmpty(Length):
    def __init__(self):
        Length.__init__(self, min=1)


class OneOf(object):
    """Validator which succeeds if ``value`` is a member of ``choices``.

    :param choices: A sequence of valid values.
    """
    _validator: validate.Validator = None

    def __init__(self, choices: Iterable):
        self._validator = validate.OneOf(choices)

    def __call__(self, value: Any) -> Any:
        return self._validator(value)


class KeyType(OneOf):
    def __init__(self):
        OneOf.__init__(self, ['prime256v1', 'rsa2048', 'sm2'])
