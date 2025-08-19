#!/usr/bin/env python3
# coding=utf-8
"""
    Copyright (C) 2020 Ant Financial. All rights reserved.

    Desc     : Aldaba2.0 Operation Tools
    History  :
    License  : Ant Financial proprietary/confidential.

    Python Version : 3.6.8
    Created by youxing.zys
    Date: 2022/12/06
"""
import click

__debug = False


def set_debug(is_debug: bool):
    global __debug
    __debug = is_debug


def echo(message, file=None):
    click.secho(message, file=file)


def debug(message, file=None):
    if __debug:
        click.secho('DEBUG: ' + message, file=file, fg='blue')


def info(message, file=None):
    click.secho('INFO: ' + message, file=file, fg='green')


def warn(message, file=None):
    click.secho('WARN: ' + message, file=file, fg='yellow')


def error(message, file=None):
    click.secho('ERROR: ' + message, file=file, err=True, fg='red')


def fatal(message, file=None):
    click.secho('FATAL: ' + message, file=file, err=True, fg='magenta')
    raise ValueError(message)
