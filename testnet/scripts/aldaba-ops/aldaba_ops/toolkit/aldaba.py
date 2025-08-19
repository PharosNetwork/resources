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
from enum import Enum


class ServiceEnum(Enum):
    DOG = 0
    PORTAL = 1
    CONTROLLER = 2
    TXPOOL = 3
    COMPUTE = 4
    LIGHT = 5


class KeyType(str, Enum):
    PRIME256V1 = "prime256v1"
    SM2 = "sm2"
    RSA = "rsa"
    BLS12381 = "bls12381"


def get_pod_uuid(service_enum: ServiceEnum, idx: int):
    import time
    return str(int(time.time() * 1_000_000)) + str(service_enum.value) + str(idx).zfill(2)
