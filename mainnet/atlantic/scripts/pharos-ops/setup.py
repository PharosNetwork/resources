#!/usr/bin/env python3
# coding=utf-8
"""A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""
import setuptools

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# 打包的目录
packages = ['pharos_ops'] + ["%s.%s" % ('pharos_ops', i) for i in setuptools.find_packages('pharos_ops')]

setuptools.setup(
    packages=packages,
    install_requires=requirements,
    tests_require=requirements
)
