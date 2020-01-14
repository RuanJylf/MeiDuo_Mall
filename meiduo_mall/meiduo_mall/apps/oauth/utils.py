import json
import urllib
from itsdangerous import TimedJSONWebSignatureSerializer as TJWSSerializer, BadData

from django.conf import settings

import logging

from . import constants
from oauth.exceptions import OAuthQQAPIError


logger = logging.getLogger('django')


class OAuthQQ(object):
    """
    QQ认证辅助工具类
    """
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None, state=None):
        # self.client_id = client_id if client_id elsea settings.QQ_CLIENT_ID
        self.client_id = client_id or settings.QQ_CLIENT_ID
        self.client_secret = client_secret or settings.QQ_CLIENT_SECRET
        self.redirect_uri = redirect_uri or settings.QQ_REDIRECT_URI
        self.state = state or settings.QQ_STATE  # 用于保存登录成功后的跳转页面路径

    def get_qq_login_url(self):
        """
        获取qq登录的网址
        :return: url网址
        """
        # 请求网址
        url = 'https://graph.qq.com/oauth2.0/authorize?'
        # 请求参数
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'state': self.state,
            'scope': 'get_user_info',
        }

        # url = 'https://graph.qq.com/oauth2.0/authorize?' + urllib.parse.urlencode(params)
        # 对url进行编码, 防止出现中文等问题
        url += urllib.parse.urlencode(params)
        return url

    def get_access_token(self, code):
        """
        获取 access_token
        :param code: qq提供的code
        :return: access_token
        """
        url = 'https://graph.qq.com/oauth2.0/token?'
        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri,
        }

        # url = 'https://graph.qq.com/oauth2.0/token?' + urllib.parse.urlencode(params)
        url += urllib.parse.urlencode(params)

        try:
            # 发送请求: urlopen(url, data), 返回response对象
            resp = urllib.request.urlopen(url)
            # 读取响应体数据: read()
            resp_data = resp.read().decode()  # bytes转str

            # access_token = FE04 ** ** ** ** ** ** ** ** ** ** ** ** CCE2
            # & expires_in = 7776000 & refresh_token = 88E4 ** ** ** ** ** ** ** ** ** ** ** ** BE14

            # 解析access_token: parse_qs()
            resp_dict = urllib.parse.parse_qs(resp_data)
        except Exception as e:
            # 记录日志, 抛出自定义异常
            logger.error('获取access_token异常: %s' % e)
            raise OAuthQQAPIError
        else:
            # 注意: 解析之后的access_token 是一个列表
            access_token = resp_dict.get('access_token')
        return access_token[0]

    def get_openid(self, access_token):
        """
        获取用户的openid
        :param access_token: qq提供的access_token
        :return: open_id
        """
        url = 'https://graph.qq.com/oauth2.0/me?access_token=' + access_token

        try:
            # 发送请求
            resp = urllib.request.urlopen(url)
            # 读取响应体数据
            resp_data = resp.read().decode()  # bytes转str

            # callback({"client_id": "YOUR_APPID", "openid": "YOUR_OPENID"});

            # 解析openid: 从{"client_id": "YOUR_APPID", "openid": "YOUR_OPENID"}中取openid
            # 切片获取{"client_id": "YOUR_APPID", "openid": "YOUR_OPENID"} json字符串
            resp_data = resp_data[10:-4]
            # 将json字符串转换成字典
            resp_dict = json.loads(resp_data)
        except Exception as e:
            logger.error('获取openid异常: %s' % e)
            raise OAuthQQAPIError
        else:
            # 从{"client_id": "YOUR_APPID", "openid": "YOUR_OPENID"}中取openid
            openid = resp_dict.get('openid')

        return openid

    def generate_bind_user_access_token(openid):
        """
        生成保存用户数据的token

        :param openid: 用户的openid
        :return: token
        """
        serializer = TJWSSerializer(settings.SECRET_KEY, constants.BIND_USER_ACCESS_TOKEN_EXPIRES)
        data = {'openid': openid}
        token = serializer.dumps(data)
        return token.decode()

    @staticmethod
    def check_bind_user_access_token(access_token):
        serializer = TJWSSerializer(settings.SECRET_KEY, constants.BIND_USER_ACCESS_TOKEN_EXPIRES)
        try:
            # data是一个字典
            data = serializer.loads(access_token)
        except BadData:
            return None
        else:
            return data['openid']
