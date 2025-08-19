import os

from aldaba_ops.toolkit import validate

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class MyGridCommonConfig(object):
    enable_adaptive: bool = field(default=True, metadata={'required': False})
    filepath: str = field(default='', metadata={'required': True, 'validate': validate.NonEmpty()})

    class Meta:
        ordered: bool = True

@dataclass
class MyGridConfig(object):
    conf: MyGridCommonConfig = field(default_factory=MyGridCommonConfig, metadata={'required': True})
    env: MyGridCommonConfig = field(default_factory=MyGridCommonConfig, metadata={'required': True})

    class Meta:
        ordered: bool = True

@dataclass
class InvalidConfigError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
