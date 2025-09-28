#!/usr/bin/env python3
# coding=utf-8
import re

tx_response_p = re.compile(r'^recv response result: ([0-9]+)$', re.M)
tx_receipt_p = re.compile(r'^{"output":(.*),"result":([0-9]+)}$', re.M)


def assertTimeout(input: str):
    if 'Timeout' in input:
        raise ValueError('case timeout!!!')


def assertTxResponse(input: str):
    print('invoke assertTxResponse')
    assertTimeout(input)
    res = tx_response_p.search(input)
    if not res:
        raise ValueError('pattern unmatch!!!')
    return res.group(1)


def assertTxReceipt(input: str):
    print('invoke assertTxReceipt')
    assertTimeout(input)
    res = tx_receipt_p.search(input)
    if not res:
        raise ValueError('pattern unmatch!!!')
    return res.group(2)


def assertBlockResponse(input: str):
    print('invoke assertBlockResponse')
    assertTimeout(input)
    return '"header" :' in input