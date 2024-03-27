from django import forms
from django.contrib import auth
from django.contrib.auth.forms import PasswordChangeForm
from django.db import models
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse
from django.utils.translation import gettext as _
from faker import Faker

from users.factories import UserFactory
from .forms import RegisterForm, ProfileUpdateForm, AdminCreateForm
from .models import User
from .views import (
    UserRegisterView,
    UserLoginView,
    UserLogoutView,
    UserListView,
    UserProfileView,
    ProfileUpdateView,
    AdminCreateView,
    UserDeleteView,
    UserResetPasswordView,
    UserStatusUpdateView,
)


# Create your tests here.
class UserModelTest(TestCase):
    def setUp(self) -> None:
        self.faker = Faker()
        self.model = User
        self.user = UserFactory().create()

    def test_first_name_has_correct_setting(self):
        field = self.model._meta.get_field("first_name")

        self.assertEqual(models.CharField, field.__class__)
        self.assertEqual(_("first name"), field.verbose_name)
        self.assertEqual(150, field.max_length)
        self.assertFalse(field.blank)

    def test_last_name_has_correct_setting(self):
        field = self.model._meta.get_field("last_name")

        self.assertEqual(models.CharField, field.__class__)
        self.assertEqual(_("last name"), field.verbose_name)
        self.assertEqual(150, field.max_length)
        self.assertFalse(field.blank)

    def test_email_has_correct_setting(self):
        field = self.model._meta.get_field("email")

        self.assertEqual(models.EmailField, field.__class__)
        self.assertEqual(_("email address"), field.verbose_name)
        self.assertFalse(field.blank)

    def test_date_updated_has_correct_setting(self):
        field = self.model._meta.get_field("date_updated")

        self.assertEqual(models.DateTimeField, field.__class__)
        self.assertTrue(field.auto_now)

    def test_required_fields_for_creating_superuser_have_correct_fields(self):
        self.assertEqual(
            ["first_name", "last_name", "email"], self.model.REQUIRED_FIELDS
        )


class RegisterFormTest(TestCase):
    def setUp(self) -> None:
        self.form = RegisterForm()

    def test_model_is_correct(self):
        self.assertEqual(User, self.form.Meta.model)

    def test_fields_are_correct(self):
        self.assertEqual(
            [
                "username",
                "first_name",
                "last_name",
                "email",
                "password",
                "confirm_password",
            ],
            self.form.Meta.fields,
        )

    def test_confirm_password_field_has_correct_setting(self):
        field = self.form.fields["confirm_password"]

        self.assertEqual(forms.CharField, field.__class__)
        self.assertEqual(_("confirm password"), field.label)
        self.assertEqual(forms.PasswordInput, field.widget.__class__)
        self.assertEqual(128, field.max_length)
        self.assertTrue(field.required)

    def test_validation_failed_when_password_and_confirm_password_mismatch(self):
        form = self.form.__class__(
            {"password": "password1", "confirm_password": "password2"}
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(
            _("Password does not match confirm password") in form["password"].errors
        )


class UserRegisterViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserRegisterView()
        self.client = Client()

    def test_url_is_correct(self):
        self.assertURLEqual("/register", reverse("users:register"))

    def test_template_name_is_correct(self):
        self.assertEqual("register.html", self.view.template_name)

    def test_form_class_is_correct(self):
        self.assertEqual(RegisterForm, self.view.form_class)

    def test_register_page_can_render(self):
        response = self.client.get(reverse("users:register"))

        self.assertEqual(200, response.status_code)

    def test_user_can_register_and_auto_login(self):
        user = UserFactory().data.copy()
        user.pop("password")

        response = self.client.post(
            reverse("users:register"),
            {**user, "password": "Passw0rd!", "confirm_password": "Passw0rd!"},
        )

        self.assertRedirects(response, expected_url=reverse("movie:list"))
        self.assertEqual(1, User.objects.filter(**user).count())
        self.assertTrue(auth.get_user(self.client).is_authenticated)


class UserLoginViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserLoginView()
        self.client = Client()
        self.user = UserFactory().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/login", reverse("users:login"))

    def test_template_is_correct(self):
        self.assertEqual("login.html", self.view.template_name)

    def test_login_page_can_render(self):
        response = self.client.get(reverse("users:login"))

        self.assertIs(200, response.status_code)

    def test_user_can_login_and_redirect_to_movies_list(self):
        response = self.client.post(
            reverse("users:login"),
            {"username": self.user.username, "password": "Passw0rd!"},
        )

        self.assertRedirects(response, expected_url=reverse("movie:list"))

    def test_inactive_user_cannot_login(self):
        inactive_user = UserFactory().inactive().create()

        response = self.client.post(
            reverse("users:login"),
            {"username": inactive_user.username, "password": "password"},
        )

        self.assertNotEqual(0, len(response.context["form"].errors))


class UserLogoutViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserLogoutView()
        self.client = Client()
        self.user = UserFactory().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/logout", reverse("users:logout"))

    def test_only_allow_post_method(self):
        self.assertEqual(["post"], self.view.http_method_names)

    def test_user_can_logout_and_redirect_to_movies_list(self):
        self.client.login(username=self.user.username, password="password")
        response = self.client.post(reverse("users:logout"))

        self.assertRedirects(response, expected_url=reverse("movie:list"))


class UserListViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserListView()
        self.client = Client()
        self.admin = UserFactory().is_superuser().create()
        self.user = UserFactory().create()

    def test_url_is_correct(self):
        self.assertEqual("/users", reverse("users:list"))

    def test_model_is_correct(self):
        self.assertEqual(User, self.view.model)

    def test_template_is_correct(self):
        self.assertEqual("user_list.html", self.view.template_name)

    def test_context_has_form(self):
        request = RequestFactory().get(reverse("users:list"))
        request.session = {}

        self.view.setup(request)
        self.view.object_list = self.view.get_queryset()
        context = self.view.get_context_data()

        self.assertIn("form", context)
        self.assertEqual(AdminCreateForm, context["form"].__class__)

    def test_form_initial_data_load_from_session_when_session_has_failed_input_data(
        self,
    ):
        failed_input = UserFactory().data.copy()
        failed_input.pop("password")
        failed_input.update({"password": "password"})

        request = RequestFactory().get(reverse("users:list"))
        request.session = {"admin-create-form": failed_input}

        self.view.setup(request)
        self.view.object_list = self.view.get_queryset()
        context = self.view.get_context_data()

        self.assertIn("form", context)
        self.assertEqual(AdminCreateForm, context["form"].__class__)
        self.assertEqual(failed_input, context["form"].data)
        self.assertIsNotNone(context["form"].errors)

    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.get(reverse("users:list"))

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:list')}",
        )

    def test_user_is_forbidden_to_access(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(reverse("users:list"))
        self.assertEqual(403, response.status_code)

    def test_admin_can_view_page(self):
        self.client.login(username=self.admin.username, password="Passw0rd!")

        response = self.client.get(reverse("users:list"))

        self.assertEqual(200, response.status_code)


class UserProfileViewTest(TestCase):
    def setUp(self) -> None:
        self.faker = Faker()
        self.view = UserProfileView()
        self.client = Client()
        self.user = UserFactory().create()
        self.admin = UserFactory().is_superuser().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/profile", reverse("users:profile"))

    def test_template_name_is_correct(self):
        self.assertEqual("profile.html", self.view.template_name)

    def test_model_is_correct(self):
        self.assertEqual(User, self.view.model)

    def test_context_has_profile_update_form(self):
        request = RequestFactory().get(reverse("users:profile"))
        request.user = self.user
        request.session = {}

        self.view.setup(request)
        self.view.object = self.user
        context = self.view.get_context_data()

        self.assertIn("profile_update_form", context)
        self.assertEqual(ProfileUpdateForm, context["profile_update_form"].__class__)
        self.assertEqual(self.user, context["profile_update_form"].instance)

    def test_context_has_reset_password_form(self):
        request = RequestFactory().get(reverse("users:profile"))
        request.session = {}
        request.user = self.user

        self.view.setup(request)
        self.view.object = self.user
        context = self.view.get_context_data()

        self.assertIn("reset_password_form", context)
        self.assertEqual(PasswordChangeForm, context["reset_password_form"].__class__)
        self.assertEqual(self.user, context["reset_password_form"].user)

    def test_profile_update_form_initial_data_load_from_session_when_session_has_failed_input_data(
        self,
    ):
        failed_input = {
            "first_name": self.faker.first_name(),
            "last_name": self.faker.last_name(),
            "email": self.faker.first_name(),
        }

        request = RequestFactory().get(reverse("users:profile"))
        request.session = {"profile-update-form": failed_input}
        request.user = self.user

        self.view.setup(request)
        self.view.object = self.user
        context = self.view.get_context_data()

        self.assertIn("profile_update_form", context)
        self.assertEqual(ProfileUpdateForm, context["profile_update_form"].__class__)
        self.assertEqual(failed_input, context["profile_update_form"].data)
        self.assertIsNotNone(context["profile_update_form"].errors)

    def test_reset_password_form_initial_data_load_from_session_when_session_has_failed_input_data(
        self,
    ):
        failed_input = {
            "old_password": "password",
            "new_password1": "NewPassw0rd!",
            "new_password2": "NewPassw0rd!",
        }

        request = RequestFactory().get(reverse("users:profile"))
        request.session = {"reset-password-form": failed_input}
        request.user = self.user

        self.view.setup(request)
        self.view.object = self.user
        context = self.view.get_context_data()

        self.assertIn("reset_password_form", context)
        self.assertEqual(PasswordChangeForm, context["reset_password_form"].__class__)
        self.assertEqual(failed_input, context["reset_password_form"].data)
        self.assertIsNotNone(context["reset_password_form"].errors)

    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.get(reverse("users:profile"))

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:profile')}",
        )

    def test_authenticated_user_can_view_profile(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(200, response.status_code)


class ProfileUpdateFormTest(TestCase):
    def setUp(self) -> None:
        self.form = ProfileUpdateForm()

    def test_model_is_correct(self):
        self.assertEqual(User, self.form.Meta.model)

    def test_fields_are_correct(self):
        self.assertEqual(
            [
                "first_name",
                "last_name",
                "email",
            ],
            self.form.Meta.fields,
        )


class ProfileUpdateViewTest(TestCase):
    def setUp(self) -> None:
        self.view = ProfileUpdateView()
        self.client = Client()
        self.user = UserFactory().create()
        self.faker = Faker()

    def test_url_is_correct(self):
        self.assertURLEqual("/profile/edit", reverse("users:edit-profile"))

    def test_form_class_is_correct(self):
        self.assertEqual(ProfileUpdateForm, self.view.form_class)

    def test_unauthenticated_user_redirects_to_login(self):
        user = {f.name: getattr(self.user, f.name) for f in self.user._meta.fields}
        user.update(
            {
                "first_name": self.faker.first_name(),
                "last_name": self.faker.last_name(),
                "email": self.faker.unique.safe_email(),
            }
        )

        response = self.client.post(
            reverse("users:edit-profile"),
            {
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
            },
        )

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:edit-profile')}",
        )

    def test_http_get_method_redirects_to_profile_page(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(reverse("users:edit-profile"))

        self.assertRedirects(response, expected_url=reverse("users:profile"))

    def test_authenticate_user_can_edit_profile_then_redirect_to_profile_page(self):
        user = {f.name: getattr(self.user, f.name) for f in self.user._meta.fields}
        user.update(
            {
                "first_name": self.faker.first_name(),
                "last_name": self.faker.last_name(),
                "email": self.faker.unique.safe_email(),
            }
        )

        self.client.login(username=self.user.username, password="Passw0rd!")
        response = self.client.post(
            reverse("users:edit-profile"),
            {
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
            },
        )

        self.assertRedirects(response, expected_url=reverse("users:profile"))
        self.assertEqual(
            1,
            User.objects.filter(
                pk=self.user.pk,
                first_name=user["first_name"],
                last_name=user["last_name"],
                email=user["email"],
            ).count(),
        )

    def test_authenticated_user_redirects_to_profile_page_and_input_data_stored_in_session_when_validation_failed(
        self,
    ):
        failed_data = {
            "first_name": self.faker.first_name(),
            "last_name": self.faker.last_name(),
            "email": self.faker.first_name(),
        }

        self.client.login(username=self.user.username, password="Passw0rd!")
        response = self.client.post(reverse("users:edit-profile"), failed_data)

        self.assertRedirects(response, reverse("users:profile"))
        self.assertIn("profile-update-form", self.client.session.keys())
        self.assertEqual(failed_data, self.client.session["profile-update-form"])


class AdminCreateFormTest(TestCase):
    def setUp(self) -> None:
        self.form = AdminCreateForm()

    def test_model_is_correct(self):
        self.assertEqual(User, self.form.Meta.model)

    def test_fields_are_correct(self):
        self.assertEqual(
            [
                "username",
                "first_name",
                "last_name",
                "email",
                "password",
            ],
            self.form.Meta.fields,
        )


class AdminCreateViewTest(TestCase):
    def setUp(self) -> None:
        self.view = AdminCreateView()
        self.client = Client()
        self.user = UserFactory().create()
        self.admin = UserFactory().is_superuser().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/users/create", reverse("users:create"))

    def test_model_is_correct(self):
        self.assertEqual(User, self.view.model)

    def test_form_class_is_correct(self):
        self.assertEqual(AdminCreateForm, self.view.form_class)

    def test_unauthenticated_user_redirects_to_login(self):
        admin = UserFactory().data.copy()
        admin.pop("password")

        response = self.client.post(
            reverse("users:create"), {**admin, "password": "Passw0rd!"}
        )

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:create')}",
        )

    def test_http_get_method_redirects_to_users_list(self):
        admin = UserFactory().data.copy()
        admin.pop("password")

        self.client.login(username=self.admin.username, password="Passw0rd!")
        response = self.client.get(reverse("users:create"))

        self.assertRedirects(response, expected_url=reverse("users:list"))

    def test_authenticated_user_is_forbidden(self):
        admin = UserFactory().data.copy()
        admin.pop("password")

        self.client.login(username=self.user.username, password="Passw0rd!")
        response = self.client.post(
            reverse("users:create"), {**admin, "password": "Passw0rd!"}
        )

        self.assertEqual(403, response.status_code)

    def test_authenticated_admin_can_create_and_new_admin_can_login(self):
        admin = UserFactory().data.copy()
        admin.pop("password")

        self.client.login(username=self.admin.username, password="Passw0rd!")
        response = self.client.post(
            reverse("users:create"), {**admin, "password": "Passw0rd!"}
        )

        self.assertRedirects(response, expected_url=reverse("users:list"))
        self.assertEqual(1, User.objects.filter(**admin, is_superuser=True).count())
        self.assertTrue(
            self.client.login(username=admin.get("username"), password="Passw0rd!")
        )


class UserDeleteViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserDeleteView
        self.client = Client()
        self.user = UserFactory().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/users/delete", reverse("users:delete"))

    def test_model_is_correct(self):
        self.assertEqual(User, self.view.model)

    def test_fields_are_correct(self):
        self.assertEqual([], self.view.fields)

    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.post(reverse("users:delete"))

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:delete')}",
        )

    def test_http_get_method_redirects_to_profile(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(reverse("users:delete"))

        self.assertRedirects(response, expected_url=reverse("users:profile"))

    def test_authenticated_user_can_delete_account_then_logout_and_redirect_to_homepage(
        self,
    ):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.post(reverse("users:delete"))

        self.assertRedirects(response, expected_url=reverse("movie:list"))
        self.assertEqual(
            1, User.objects.filter(pk=self.user.pk, is_active=False).count()
        )
        self.assertFalse(auth.get_user(self.client).is_authenticated)


class UserResetPasswordViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserResetPasswordView
        self.client = Client()
        self.user = UserFactory().create()

    def test_url_is_correct(self):
        self.assertURLEqual("/reset-password", reverse("users:reset-password"))

    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.post(
            reverse("users:reset-password"),
            {
                "old_password": "Passw0rd!",
                "new_password1": "NewPassw0rd!",
                "new_password2": "NewPassw0rd!",
            },
        )

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:reset-password')}",
        )

    def test_http_get_method_redirects_to_profile_page(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(reverse("users:reset-password"))

        self.assertRedirects(response, expected_url=reverse("users:profile"))

    def test_authenticated_user_can_reset_password_and_redirect_to_profile(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.post(
            reverse("users:reset-password"),
            {
                "old_password": "Passw0rd!",
                "new_password1": "NewPassw0rd!",
                "new_password2": "NewPassw0rd!",
            },
        )

        self.assertRedirects(response, expected_url=reverse("users:profile"))
        self.assertTrue(
            self.client.login(username=self.user.username, password="NewPassw0rd!")
        )

    def test_redirect_to_profile_page_with_failed_input_when_validation_failed(self):
        failed_input = {
            "old_password": "password",
            "new_password1": "NewPassw0rd!",
            "new_password2": "NewPassw0rd!",
        }

        self.client.login(username=self.user.username, password="Passw0rd!")
        response = self.client.post(reverse("users:reset-password"), failed_input)

        self.assertRedirects(
            response, expected_url=f"{reverse('users:profile')}#reset-password"
        )
        self.assertIn("reset-password-form", self.client.session.keys())
        self.assertEqual(failed_input, self.client.session["reset-password-form"])


class UserStatusUpdateViewTest(TestCase):
    def setUp(self) -> None:
        self.view = UserStatusUpdateView()
        self.client = Client()
        self.user = UserFactory().create()
        self.admin = UserFactory().is_superuser().create()

    def test_url_is_correct(self):
        self.assertEqual(
            "/users/1/status", reverse("users:toggle-status", kwargs={"pk": 1})
        )

    def test_model_is_correct(self):
        self.assertEqual(User, self.view.model)

    def test_fields_are_correct(self):
        self.assertEqual([], self.view.fields)

    def test_unauthenticated_user_redirects_to_login(self):
        response = self.client.post(
            reverse("users:toggle-status", kwargs={"pk": self.user.pk})
        )

        self.assertRedirects(
            response,
            expected_url=f"{reverse('users:login')}?next={reverse('users:toggle-status', kwargs={'pk': self.user.pk})}",
        )

    def test_http_get_method_redirects_to_profile(self):
        self.client.login(username=self.admin.username, password="Passw0rd!")

        response = self.client.get(
            reverse("users:toggle-status", kwargs={"pk": self.user.pk})
        )

        self.assertRedirects(response, expected_url=reverse("users:list"))

    def test_authenticated_user_is_forbidden(self):
        self.client.login(username=self.user.username, password="Passw0rd!")

        response = self.client.get(
            reverse("users:toggle-status", kwargs={"pk": self.admin.pk})
        )

        self.assertEqual(403, response.status_code)

    def test_authenticated_admin_is_forbidden_to_toggle_own_status(self):
        self.client.login(username=self.admin.username, password="Passw0rd!")

        response = self.client.get(
            reverse("users:toggle-status", kwargs={"pk": self.admin.pk})
        )

        self.assertEqual(403, response.status_code)

    def test_authenticated_user_can_toggle_other_user_status_and_redirect_to_users_list(
        self,
    ):
        self.client.login(username=self.admin.username, password="Passw0rd!")

        response = self.client.post(
            reverse("users:toggle-status", kwargs={"pk": self.user.pk})
        )

        self.assertRedirects(response, expected_url=reverse("users:list"))
        self.assertEqual(
            1, User.objects.filter(pk=self.user.pk, is_active=False).count()
        )

        response = self.client.post(
            reverse("users:toggle-status", kwargs={"pk": self.user.pk})
        )

        self.assertRedirects(response, expected_url=reverse("users:list"))
        self.assertEqual(
            1, User.objects.filter(pk=self.user.pk, is_active=True).count()
        )
