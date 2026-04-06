"""Agency code and article category enums.

Both enums subclass `str` so existing string comparisons (including values
loaded from `agencies.json` and values persisted to the DB) keep working
without explicit `.value` access.
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


SANCTION_AGENCY_CODES: frozenset = frozenset(
    {AgencyCode.FSS_SANCTION, AgencyCode.FSS_MGMT_NOTICE}
)


class ArticleCategory(str, Enum):
    PRESS_RELEASE = "press_release"
    REGULATION_NOTICE = "regulation_notice"
    SANCTION_NOTICE = "sanction_notice"
