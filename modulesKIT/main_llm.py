#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Luraminaki
"""

from modulesKIT.modules.helpers.generic_app import generic_launcher
from modulesKIT.modules.llm import api_views

if __name__ == "__main__":
    generic_launcher(__file__, api_views.LlmView)

# fastapi dev main_llm.py
