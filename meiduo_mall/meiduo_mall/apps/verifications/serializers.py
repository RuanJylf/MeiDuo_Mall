from django_redis import get_redis_connection
from redis import RedisError
from rest_framework import serializers


# 继承serializers.Serializer , 是因为image_code_id, text是自定义的参数
# 没有模板序列化器可用, 所以不继承ModelSerializer
class ImageCodeCheckSerializer(serializers.Serializer):
    """
    图片验证码校验序列化器
    校验image_code_id, text 查询字符串参数
    """
    image_code_id = serializers.UUIDField()
    text = serializers.CharField(max_length=4, min_length=4)

    # validate: 可以跨字段进行校验, 校验多个字段参数
    # validate_字段: 针对特定的字段进行校验, 只能校验一个字段参数
    def validate(self, attrs):
        """
        校验
        """
        image_code_id = attrs['image_code_id']
        text = attrs['text']

        # 查询真实图片验证码
        redis_conn = get_redis_connection('verify_codes')
        real_image_code_text = redis_conn.get('img_%s' % image_code_id)
        if not real_image_code_text:
            # 如果没取到, 说明验证码不存在或者验证码已过期
            raise serializers.ValidationError('图片验证码无效')

        # 删除redis中的图片验证码
        redis_conn.delete('img_%s' % image_code_id)

        # 比较图片验证码
        real_image_code_text = real_image_code_text.decode()
        if real_image_code_text.lower() != text.lower():
            raise serializers.ValidationError('图片验证码错误')

        # 判断短信发送时间是否在60s内
        # get_serializer 方法在创建序列化器对象的时候, 会补充context属性
        # context 属性中包含三个值 request, format格式, view类视图对象
        # self.context['view'] 获取当前序列化器的类视图对象

        # django 的类视图对象中, kwargs(字典)属性保存路径提取出来的参数mobile
        mobile = self.context['view'].kwargs['mobile']

        # 获取手机号短信发送记录
        send_flag = redis_conn.get("send_flag_%s" % mobile)
        if send_flag:
            # 如果send_flag记录已存在, 说明60s之内已发送验证码
            raise serializers.ValidationError('请求次数过于频繁')

        return attrs
