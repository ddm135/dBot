import re

USER_AGENT_ANDROID = "Android"
USER_AGENT_MACINTOSH = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.14 "
    "Mobile/15E148 "
    "Safari/604.1"
)
USER_AGENTS = (USER_AGENT_ANDROID, USER_AGENT_MACINTOSH)
REG_EXP = re.compile(r"var mac_redirect = '(.*?)';")
