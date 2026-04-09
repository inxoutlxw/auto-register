"""密码生成器，根据配置规则生成符合要求的随机密码。"""

import random
import string
from dataclasses import dataclass


@dataclass
class PasswordPolicy:
    """密码策略配置。"""

    length: int = 14
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True


def generate_password(policy: PasswordPolicy | None = None) -> str:
    """根据密码策略生成随机密码。

    确保至少包含策略要求的每种字符类型各一个，其余随机填充。

    Args:
        policy: 密码策略，为 None 时使用默认策略。

    Returns:
        生成的密码字符串。
    """
    if policy is None:
        policy = PasswordPolicy()

    # 构建必选字符池和必选字符
    mandatory: list[str] = []
    pool = ""

    if policy.require_uppercase:
        mandatory.append(random.choice(string.ascii_uppercase))
        pool += string.ascii_uppercase

    if policy.require_lowercase:
        mandatory.append(random.choice(string.ascii_lowercase))
        pool += string.ascii_lowercase

    if policy.require_digits:
        mandatory.append(random.choice(string.digits))
        pool += string.digits

    # 如果无任何要求，默认使用字母+数字
    if not pool:
        pool = string.ascii_letters + string.digits

    # 填充剩余长度
    remaining = max(0, policy.length - len(mandatory))
    fill = random.choices(pool, k=remaining)

    # 合并并打乱
    result = mandatory + fill
    random.shuffle(result)

    return "".join(result)
