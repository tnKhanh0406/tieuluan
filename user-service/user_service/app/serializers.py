from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'first_name', 'last_name', 'role']
        extra_kwargs = {
            'role': {'required': False},
        }

    def validate_role(self, value):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            if value != User.ROLE_CUSTOMER:
                raise serializers.ValidationError('Chỉ cho phép tự đăng ký với role customer.')
        return value

    def create(self, validated_data):
        role = validated_data.pop('role', User.ROLE_CUSTOMER)
        user = User(**validated_data)
        user.role = role
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError('Tên đăng nhập hoặc mật khẩu không đúng.')
        attrs['user'] = user
        return attrs
