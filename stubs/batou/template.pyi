from io import StringIO
from typing import Any

from jinja2.environment import Environment

from batou.component import ConfigString

class TemplateEngine:
    @classmethod
    def get(cls, enginename: str) -> Jinja2Engine: ...
    def _render_template_file(
        self,
        sourcefile: str,
        args: dict[str, Any],  # Any: template context values are heterogeneous
    ) -> StringIO: ...
    def expand(
        self,
        templatestr: str,
        args: dict[str, Any],
    ) -> str: ...  # Any: template context values
    def template(
        self,
        sourcefile: str,
        args: dict[str, Any],
    ) -> str: ...  # Any: template context values

class Jinja2Engine(TemplateEngine):
    env: Environment

    def __init__(
        self,
        *args: object,
        **kwargs: object,
    ) -> None: ...
    def _render_template_file(
        self,
        sourcefile: str,
        args: dict[str, Any],  # Any: template context values are heterogeneous
    ) -> StringIO: ...
    def expand(
        self,
        templatestr: str | ConfigString,
        args: dict[str, Any],  # Any: template context values are heterogeneous
        identifier: str = ...,
    ) -> str: ...
