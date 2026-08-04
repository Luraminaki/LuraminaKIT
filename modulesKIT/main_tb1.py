#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Luraminaki
"""

from modulesKIT.modules.helpers.generic_app import generic_launcher
from modulesKIT.modules.tb1 import api_views

if __name__ == "__main__":
    generic_launcher(__file__, api_views.TB1View)

# fastapi dev main_tb1.py
