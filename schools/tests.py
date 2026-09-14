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
        # Alphabet is lowercase and free of ambiguous characters.
        self.assertEqual(code, code.lower())
        for bad in "loi01":
            self.assertNotIn(bad, ACCESS_CODE_ALPHABET)

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


class StudentNumberTests(TestCase):
    def test_students_get_sequential_numbers_per_class(self):
        teacher = make_teacher("num@example.com")
        school_class = make_class(teacher)
        s1 = Student.objects.create(school_class=school_class, display_name="A")
        s2 = Student.objects.create(school_class=school_class)
        self.assertEqual(s1.number, 1)
        self.assertEqual(s2.number, 2)
        self.assertEqual(s2.number_label, "#002")

    def test_label_falls_back_to_number(self):
        teacher = make_teacher("num2@example.com")
        school_class = make_class(teacher)
        anon = Student.objects.create(school_class=school_class)
        self.assertEqual(anon.label, "#001")


class StudentLoginTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # rate-limit counters live in the process cache
        self.teacher = make_teacher("t4@example.com")
        self.school_class = make_class(self.teacher)
        self.student = Student.objects.create(
            school_class=self.school_class, display_name="Clara"
        )

    def test_start_page_redirects_to_token_url(self):
        response = self.client.post(
            reverse("schools:student_login"),
            {"access_code": self.student.access_code.upper()},  # case-insensitive
        )
        self.assertRedirects(
            response,
            reverse("schools:student_space", args=[self.student.access_code]),
        )

    def test_token_url_logs_in_directly(self):
        # This is what the QR code points at.
        response = self.client.get(
            reverse("schools:student_space", args=[self.student.access_code])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clara")

    def test_invalid_token_url_redirects_to_start(self):
        response = self.client.get(
            reverse("schools:student_space", args=["nichtvorhanden"])
        )
        self.assertRedirects(response, reverse("schools:student_login"))

    def test_login_with_invalid_code(self):
        response = self.client.post(
            reverse("schools:student_login"), {"access_code": "nope23456789"}
        )
        self.assertContains(response, "ungültig")

    def test_deactivated_student_cannot_login(self):
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        response = self.client.get(
            reverse("schools:student_space", args=[self.student.access_code]),
            follow=True,
        )
        self.assertContains(response, "ungültig")

    def test_rate_limiting_blocks_after_10_failures(self):
        from django.core.cache import cache

        cache.clear()
        url = reverse("schools:student_login")
        for _ in range(10):
            self.client.post(url, {"access_code": "wrong2345678"})
        response = self.client.post(url, {"access_code": "wrong2345678"})
        self.assertContains(response, "Zu viele Fehlversuche")


class QrDocumentTests(TestCase):
    def test_owner_can_open_qr_document(self):
        teacher = make_teacher("qr@example.com")
        school_class = make_class(teacher)
        student = Student.objects.create(school_class=school_class, display_name="Eve")
        self.client.force_login(teacher)
        response = self.client.get(
            reverse("schools:class_qr_document", args=[school_class.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, student.access_code)
        self.assertContains(response, "<svg")  # QR rendered inline

    def test_non_member_cannot_open_qr_document(self):
        owner = make_teacher("qrowner@example.com")
        other = make_teacher("qrother@example.com")
        school_class = make_class(owner)
        self.client.force_login(other)
        response = self.client.get(
            reverse("schools:class_qr_document", args=[school_class.pk])
        )
        self.assertEqual(response.status_code, 404)


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
