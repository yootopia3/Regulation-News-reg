"""Agency code and article category enums.

Both enums subclass ``str`` so existing string comparisons (including values
loaded from ``agencies.json`` and values persisted to the DB) keep working
without explicit ``.value`` access.

**Python 3.11+ gotcha**: from 3.11 onwards ``str(Enum.MEMBER)`` returns
``"EnumName.MEMBER"`` instead of the raw value. That broke
``supabase-py`` queries such as ``.eq('agency', AgencyCode.FSS_SANCTION)``
because the client calls ``str()`` on the parameter when building the URL,
producing the literal string ``"AgencyCode.FSS_SANCTION"`` and matching no
rows. ``StrEnum`` (3.11+) fixes this but is unavailable on Python 3.10
which is what the GitHub Actions workflow pins. The portable fix is to
override ``__str__`` ourselves.
"""

from enum import Enum


class AgencyCode(str, Enum):
    FSC = "FSC"
    MOEF = "MOEF"
    FSS = "FSS"
    BOK = "BOK"
    FSS_REG = "FSS_REG"
    FSC_REG = "FSC_REG"
    FSS_REG_INFO = "FSS_REG_INFO"
    FSS_SANCTION = "FSS_SANCTION"
    FSS_MGMT_NOTICE = "FSS_MGMT_NOTICE"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


SANCTION_AGENCY_CODES: frozenset = frozenset(
    {AgencyCode.FSS_SANCTION, AgencyCode.FSS_MGMT_NOTICE}
)


class ArticleCategory(str, Enum):
    PRESS_RELEASE = "press_release"
    REGULATION_NOTICE = "regulation_notice"
    SANCTION_NOTICE = "sanction_notice"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value
