# shared/__init__.py
# Makes `shared` a Python package so consumers can do:
#   import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
#   from shared.wxo_span import count_tokens, get_bearer_token, build_otlp_payload, post_to_wxo
