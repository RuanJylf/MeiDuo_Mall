from django.shortcuts import render

# Create your views here.


#  url(r'^qq/authorization/$', views.QQAuthURLView.as_view()),
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings

from oauth.exceptions import OAuthQQAPIError
from oauth.models import OAuthQQUser
from oauth.utils import OAuthQQ
from .serializers import OAuthQQUserSerializer


class QQAuthURLView(APIView):
    """
    获取QQ登录的url  ?next=xxx
    """
    def get(self, request):
        """
        提供用于qq登录的url  ?next=xxx
        """
        # 从查询字符串获取next参数
        next = request.query_params.get('next')

        # 拼接QQ登录的网址, 封装工具类
        oauth_qq = OAuthQQ(state=next)
        login_url = oauth_qq.get_qq_login_url()

        # 返回
        return Response({'login_url': login_url})


# CreateView 用于注册创建用户
class QQAuthUserView(CreateAPIView):
    """
    QQ登录的用户  ?code=xxx
    """
    serializer_class = OAuthQQUserSerializer

    def get(self, request):
        """
        获取qq登录的用户数据
        """
        # 获取code
        code = request.query_params.get('code')
        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)

        # 凭借code, 获取access_token
        oauth_qq = OAuthQQ()
        # 获取用户openid
        try:
            access_token = oauth_qq.get_access_token(code)
            # 凭借access_token获取 openid
            openid = oauth_qq.get_openid(access_token)
        except OAuthQQAPIError:
            return Response({'message': '访问QQ接口异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 根据openid查询数据库OAuthQQUser, 判断数据是否存在
        try:
            oauth_qq_user = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 如果数据不存在, 处理 openid 并返回
            # 用户第一次使用QQ登录, 绑定并创建用户
            access_token = oauth_qq.generate_bind_user_access_token(openid)
            return Response({'access_token': access_token})
        else:
            # 如果数据存在, 表示用户已经绑定过身份, 签发JWT token
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            user = oauth_qq_user.user
            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)

            response = Response({
                'token': token,
                'user_id': user.id,
                'username': user.username
            })
            return response

    # def post(self, request):
    #     # 由序列化器完成
    #     # 获取参数
    #     # 校验参数
    #     # 判断用户是否存在
    #     # 如果存在, 绑定, 创建OAuthQQUser 数据
    #     # 如果不存在, 先创建User, 创建OAuthQQUser数据
    #     # 签发JWT token
    #     pass
