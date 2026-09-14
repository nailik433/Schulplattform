from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    ACCESS_CODE_ALPHABET,
    ClassMembership,
    School,
    SchoolClass,
    Student,
    generate_access_code,
)

User = get_user_model()


def make_teacher(email, password="testpass123", school=None):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Test",
        last_name="Lehrer",
        school=school,
    )


def make_class(teacher, name="5a", subject="Informatik"):
    # The class lives in the teacher's school; create one if needed and make
    # sure the teacher is assigned to it (mirrors the invitation flow).
    school = teacher.school or School.objects.create(name="Testschule")
    if teacher.school_id != school.id:
        teacher.school = school
        teacher.save(update_fields=["school"])
    school_class = SchoolClass.objects.create(school=school, name=name, subject=subject)
    ClassMembership.objects.create(
        school_class=school_class, teacher=teacher, role=ClassMembership.Role.OWNER
    )
    return school_class


class AccessCodeTests(TestCase):
    def test_generated_code_length_and_alphabet(self):
        code = generate_access_code()
        self.assertEqual(len(code), 8)
        self.assertTrue(all(ch in ACCESS_CODE_ALPHABET for ch in code))

    def test_student_gets_code_on_save(self):
        teacher = make_teacher("t1@example.com")
        school_class = make_class(teacher)
        student = Student.objects.create(school_class=school_class, display_name="Anna")
        self.assertTrue(student.access_code)

    def test_codes_are_unique(self):
        teacher = make_teacher("t2@example.com")
        school_class = make_class(teacher)
        codes = {
            Student.objects.create(
                school_class=school_class, display_name=f"S{i}"
            ).access_code
            for i in range(25)
        }
        self.assertEqual(len(codes), 25)

    def test_regenerate_changes_code(self):
        teacher = make_teacher("t3@example.com")
        school_class = make_class(teacher)
        student = Student.objects.create(school_class=school_class, display_name="Ben")
        old = student.access_code
        student.regenerate_access_code()
        self.assertNotEqual(old, student.access_code)


class ClassOwnershipTests(TestCase):
    def test_owner_property(self):
        teacher = make_teacher("owner@example.com")
        school_class = make_class(teacher)
        self.assertEqual(school_class.owner, teacher)

    def test_teacher_cannot_open_foreign_class(self):
        owner = make_teacher("owner2@example.com")
        other = make_teacher("other@example.com")
        school_class = make_class(owner)

        self.client.force_login(other)
        response = self.client.get(
            reverse("schools:class_detail", args=[school_class.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_open_own_class(self):
        owner = make_teacher("owner3@example.com")
        school_class = make_class(owner)
        self.client.force_login(owner)
        response = self.client.get(
            reverse("schools:class_detail", args=[school_class.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_collaborator_sees_class_but_not_others(self):
        owner = make_teacher("owner4@example.com")
        colleague = make_teacher("colleague@example.com")
        shared = make_class(owner, name="5a")
        private = make_class(owner, name="6b")

        # Simulate the future "share" feature.
        ClassMembership.objects.create(
            school_class=shared,
            teacher=colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )

        self.client.force_login(colleague)
        self.assertEqual(
            self.client.get(reverse("schools:class_detail", args=[shared.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("schools:class_detail", args=[private.pk])).status_code,
            404,
        )


class StudentLoginTests(TestCase):
    def test_login_with_valid_code(self):
        teacher = make_teacher("t4@example.com")
        school_class = make_class(teacher)
        student = Student.objects.create(school_class=school_class, display_name="Clara")

        response = self.client.post(
            reverse("schools:student_login"),
            {"access_code": student.access_code.lower()},  # case-insensitive
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clara")

    def test_login_with_invalid_code(self):
        response = self.client.post(
            reverse("schools:student_login"), {"access_code": "NOPE1234"}
        )
        self.assertContains(response, "ungültig")

    def test_deactivated_student_cannot_login(self):
        teacher = make_teacher("t5@example.com")
        school_class = make_class(teacher)
        student = Student.objects.create(
            school_class=school_class, display_name="Dora", is_active=False
        )
        response = self.client.post(
            reverse("schools:student_login"), {"access_code": student.access_code}
        )
        self.assertContains(response, "ungültig")


class ClassCreateTests(TestCase):
    def test_teacher_creates_class_in_own_school(self):
        school = School.objects.create(name="Meine Schule")
        teacher = make_teacher("owns@example.com", school=school)
        self.client.force_login(teacher)
        response = self.client.post(
            reverse("schools:class_create"),
            {"name": "7c", "subject": "Mathe"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = SchoolClass.objects.get(name="7c")
        self.assertEqual(created.school, school)
        self.assertEqual(created.owner, teacher)

    def test_teacher_without_school_cannot_create_class(self):
        teacher = make_teacher("noschool@example.com", school=None)
        self.client.force_login(teacher)
        response = self.client.post(
            reverse("schools:class_create"), {"name": "7c"}, follow=True
        )
        self.assertFalse(SchoolClass.objects.filter(name="7c").exists())
