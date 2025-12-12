#!/usr/bin/env python3
# coding=utf-8

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from marshmallow_dataclass import class_schema


@dataclass
class Assert(object):
    action: str = field(default='', metadata={'required': True})
    expect: Any = field(default='', metadata={'required': True})

    class Meta:
        ordered: bool = True


@dataclass
class Command(object):
    command: str = field(default='', metadata={'required': True})
    args: List[str] = field(default_factory=list, metadata={'required': False})
    asserts: List[Assert] = field(default_factory=list, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class Stage(object):
    name: str = field(default='', metadata={'required': True})
    template: str = field(default='', metadata={'required': False})
    description: str = field(default='', metadata={'required': True})
    workspace: str = field(default='', metadata={'required': False})
    next: str = field(default='', metadata={'required': False})
    error: str = field(default='', metadata={'required': False})
    end: bool = field(default=False, metadata={'required': False})
    pre: Command = field(default_factory=Command, metadata={'required': False})
    post: Command = field(default_factory=Command, metadata={'required': False})
    runs_type: str = field(default='', metadata={'required': False})
    runs: List[Command] = field(default_factory=list, metadata={'required': False})

    class Meta:
        ordered: bool = True


@dataclass
class Flow(object):
    """Data class of BVT_DSL.json"""

    action_scripts: str = field(default='', metadata={'required': True})
    envs: Dict[str, str] = field(default_factory=dict, metadata={'required': False})
    start_stage: str = field(default='', metadata={'required': False})
    stages: List[Stage] = field(default_factory=list, metadata={'required': True})

    class Meta:
        ordered: bool = True


FlowSchema = class_schema(Flow)
StageSchema = class_schema(Stage)
