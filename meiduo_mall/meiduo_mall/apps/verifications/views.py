import logging
import random

from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from celery_tasks.sms.tasks import send_sms_code
from meiduo_mall.libs.captcha.captcha import captcha
from meiduo_mall.utils.yuntongxun.sms import CCP
from verifications import constants
from verifications.serializers import ImageCodeCheckSerializer

logger = logging.getLogger('django')


# 不使用序列化器, 所以继承基类APIView
class ImageCodeView(APIView):
    """图片验证码"""

    # 访问方式： GET /image_codes/(?P<image_code_id>[\w-]+)/
    def get(self, request, image_code_id):

        # 接收参数, 路由正则匹配完成
        # 校验参数, 不需要序列化器, 正则匹配校验
        # 生成验证码图片和文本真实值, 由第三方工具包captcha生成
        text, image = captcha.generate_captcha()
        print(text)

        # 保存验证码真实值
        redis_conn = get_redis_connection('verify_codes')
        redis_conn.setex("img_%s" % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        # 固定返回验证码图片数据，不需要REST framework框架的Response中的renderer渲染器返回响应数据的格式
        # 所以此处直接使用Django原生的HttpResponse即可
        return HttpResponse(image, content_type='image/jpg')


# url('^sms_codes/(?P<mobile>1[3-9]\d{9})/$', views.SMSCodeView.as_view()),
# 仅使用序列化器的基本校验功能, 不需要其他扩展, 所以继承基类GenericAPIView
class SMSCodeView(GenericAPIView):
    """
    短信验证码
    传入参数：
        mobile: 路径参数
        image_code_id, text : 查询字符串参数
    """
    serializer_class = ImageCodeCheckSerializer

    def get(self, request, mobile):
        # 接受参数, 校验参数, 由序列化器完成
        # image_code_id, text 存放在 request.query_params 里
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        # 生成短信验证码
        sms_code = "%06d" % random.randint(0, 999999)
        print(sms_code)

        # 保存短信验证码与发送记录
        redis_conn = get_redis_connection('verify_codes')
        # redis_conn.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # redis_conn.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        # redis 管道, 管道执行的命令, 要么全成功, 要么全失败
        pl = redis_conn.pipeline()
        # 收集打包多条 redis 的执行命令成一条命令, 提高执行效率
        pl.setex("sms_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        pl.setex("send_flag_%s" % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)
        # 让管道通知redis批量执行命令
        pl.execute()

        # # 发送短信验证码
        # try:
        #     ccp = CCP()
        #     expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        #     result = ccp.send_template_sms(mobile, [sms_code, expires], constants.SMS_CODE_TEMP_ID)
        # except Exception as e:
        #     logger.error("发送验证码短信[异常][ mobile: %s, message: %s ]" % (mobile, e))
        #     return Response({"message": "failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # else:
        #     if result == 0:
        #         logger.info("发送验证码短信[正常][ mobile: %s ]" % mobile)
        #         # 发送成功, 状态码默认为200
        #         return Response({"message": "OK"})
        #     else:
        #         logger.warning("发送验证码短信[失败][ mobile: %s ]" % mobile)
        #         return Response({"message": "failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 使用celery发送短信验证码
        expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        # 将send_sms_code添加到任务队列中
        send_sms_code.delay(mobile, sms_code, expires, constants.SMS_CODE_TEMP_ID)

        return Response({"message": "OK"})
