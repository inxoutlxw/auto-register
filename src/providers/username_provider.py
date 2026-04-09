"""随机用户名生成器。"""

import random
import string


class UsernameProvider:
    """生成随机用户名。"""

    def __init__(self, prefix: str = "user", length: int = 8):
        self._prefix = prefix
        self._length = length

    def get(self) -> str:
        """生成并返回随机用户名，格式：{prefix}_{随机后缀}。"""
        chars = string.ascii_lowercase + string.digits
        suffix = "".join(random.choices(chars, k=self._length))
        return f"{self._prefix}_{suffix}"
