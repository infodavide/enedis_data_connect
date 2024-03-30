#!/usr/bin/python3
# -*- coding: utf-8-
"""
The utilities of the custom component
"""


class Singleton(type):
    """
    Singleton class
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Interceptor
        :param args: the class
        :param kwargs: tje parameters
        :return: the instance
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
