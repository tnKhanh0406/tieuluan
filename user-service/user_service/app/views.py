from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .permissions import IsAdminRole
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
	queryset = User.objects.all()
	serializer_class = RegisterSerializer
	permission_classes = [AllowAny]


class LoginView(APIView):
	permission_classes = [AllowAny]

	def post(self, request):
		serializer = LoginSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		user = serializer.validated_data['user']
		token, _ = Token.objects.get_or_create(user=user)
		return Response(
			{
				'token': token.key,
				'user': UserSerializer(user).data,
			},
			status=status.HTTP_200_OK,
		)


class UserListView(generics.ListAPIView):
	queryset = User.objects.all().order_by('id')
	serializer_class = UserSerializer
	permission_classes = [IsAdminRole]
