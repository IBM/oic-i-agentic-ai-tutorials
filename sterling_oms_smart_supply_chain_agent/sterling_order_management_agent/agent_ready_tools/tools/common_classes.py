from typing import Union

from pydantic import BaseModel
from pydantic_extra_types.currency_code import ISO4217  # pants: no-infer-dep


class Currency(BaseModel):
    """Represents a currency by ISO code."""

    # TODO(DanielD): Remove once the mypy can detect the type correctly.
    code: Union[ISO4217, str]
    "A three-letter currency code as defined by ISO 4217. Examples: 'USD' for US Dollar or 'EUR' for Euro."
