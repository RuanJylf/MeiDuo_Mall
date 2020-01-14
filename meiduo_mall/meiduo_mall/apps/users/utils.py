import re
from django.contrib.auth.backends import ModelBackend

from users.models import User


def jwt_response_payload_handler(token, user=None, request=None):
    """
    自定义jwt认证成功返回数据
    """
    return {
        'token': token,
        'user_id': user.id,
        'username': user.username
    }


def get_user_by_account(account):
    """
    根据帐号获取user用户对象
    :param account: 账号，可以是用户名，也可以是手机号
    :return: User对象 或者 None
    """
    try:
        if re.match('^1[3-9]\d{9}$', account):
            # 帐号为手机号
            user = User.objects.get(mobile=account)
        else:
            # 帐号为用户名
            user = User.objects.get(username=account)
    except User.DoesNotExist:
        return None
    else:
        return user


class UsernameMobileAuthBackend(ModelBackend):
    """
    自定义用户名或手机号认证, 实现多账号登录
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 获取用户对象, username可能是用户名, 也可能是手机号
        user = get_user_by_account(username)

        # 如果用户对象存在, 校验密码
        if user is not None and user.check_password(password):
            return user
        # 如果不存在, 不做处理, 默认返回None
