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
        self.assertEqual(len(code), 6)
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


class ClassSharingTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Gemeinsame Schule")
        self.owner = make_teacher("owner@share.de", school=self.school)
        self.colleague = make_teacher("kollege@share.de", school=self.school)
        self.school_class = make_class(self.owner)  # owner's class in self.school

    def _share_url(self):
        return reverse("schools:class_share_add", args=[self.school_class.pk])

    def test_owner_can_share_with_colleague(self):
        self.client.force_login(self.owner)
        self.client.post(self._share_url(), {"email": "KOLLEGE@share.de"})
        self.assertTrue(
            ClassMembership.objects.filter(
                school_class=self.school_class,
                teacher=self.colleague,
                role=ClassMembership.Role.COLLABORATOR,
            ).exists()
        )

    def test_colleague_then_sees_and_opens_class(self):
        ClassMembership.objects.create(
            school_class=self.school_class,
            teacher=self.colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        self.client.force_login(self.colleague)
        # Dashboard lists it, class detail opens.
        self.assertContains(self.client.get(reverse("schools:dashboard")), self.school_class.name)
        self.assertEqual(
            self.client.get(self.school_class.get_absolute_url()).status_code, 200
        )

    def test_sharing_unknown_email_does_nothing(self):
        self.client.force_login(self.owner)
        self.client.post(self._share_url(), {"email": "niemand@share.de"})
        self.assertEqual(self.school_class.memberships.count(), 1)  # only owner

    def test_cannot_share_across_schools(self):
        outsider = make_teacher("extern@other.de", school=School.objects.create(name="Andere"))
        self.client.force_login(self.owner)
        self.client.post(self._share_url(), {"email": outsider.email})
        self.assertFalse(
            ClassMembership.objects.filter(
                school_class=self.school_class, teacher=outsider
            ).exists()
        )

    def test_collaborator_cannot_manage_sharing(self):
        ClassMembership.objects.create(
            school_class=self.school_class,
            teacher=self.colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        third = make_teacher("dritte@share.de", school=self.school)
        self.client.force_login(self.colleague)
        response = self.client.post(self._share_url(), {"email": third.email})
        self.assertEqual(response.status_code, 404)  # not an owner
        self.assertFalse(
            ClassMembership.objects.filter(
                school_class=self.school_class, teacher=third
            ).exists()
        )

    def test_owner_can_remove_collaborator(self):
        ClassMembership.objects.create(
            school_class=self.school_class,
            teacher=self.colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        self.client.force_login(self.owner)
        self.client.post(
            reverse(
                "schools:class_share_remove",
                args=[self.school_class.pk, self.colleague.pk],
            )
        )
        self.assertFalse(
            ClassMembership.objects.filter(
                school_class=self.school_class, teacher=self.colleague
            ).exists()
        )

    def test_collaborator_does_not_see_owners_other_class(self):
        other_class = make_class(self.owner, name="andere")
        ClassMembership.objects.create(
            school_class=self.school_class,
            teacher=self.colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        self.client.force_login(self.colleague)
        self.assertEqual(
            self.client.get(other_class.get_absolute_url()).status_code, 404
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

    def test_label_falls_back_to_seat_label(self):
        teacher = make_teacher("num2@example.com")
        school_class = make_class(teacher)  # name "5a"
        anon = Student.objects.create(school_class=school_class)
        self.assertEqual(anon.label, "5a-001")
        self.assertEqual(anon.seat_label, "5a-001")
        self.assertEqual(anon.number_padded, "001")


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


class StudentBulkDeleteTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("bulk@example.com")
        self.school_class = make_class(self.teacher)
        self.s1 = Student.objects.create(school_class=self.school_class)
        self.s2 = Student.objects.create(school_class=self.school_class)
        self.s3 = Student.objects.create(school_class=self.school_class)
        self.client.force_login(self.teacher)

    def test_bulk_delete_selected(self):
        self.client.post(
            reverse("schools:student_bulk_delete", args=[self.school_class.pk]),
            {"student_ids": [self.s1.pk, self.s3.pk]},
        )
        remaining = set(self.school_class.students.values_list("pk", flat=True))
        self.assertEqual(remaining, {self.s2.pk})

    def test_bulk_delete_nothing_selected(self):
        self.client.post(
            reverse("schools:student_bulk_delete", args=[self.school_class.pk]), {}
        )
        self.assertEqual(self.school_class.students.count(), 3)

    def test_cannot_bulk_delete_other_class_students(self):
        other = make_class(make_teacher("other2@example.com"), name="9z")
        victim = Student.objects.create(school_class=other)
        self.client.post(
            reverse("schools:student_bulk_delete", args=[self.school_class.pk]),
            {"student_ids": [victim.pk]},
        )
        # Students of a different class are not affected.
        self.assertTrue(Student.objects.filter(pk=victim.pk).exists())


class ClassDeleteTests(TestCase):
    def setUp(self):
        self.owner = make_teacher("delowner@example.com")
        self.school_class = make_class(self.owner)
        Student.objects.create(school_class=self.school_class)

    def test_delete_requires_exact_word(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("schools:class_delete", args=[self.school_class.pk]),
            {"confirm": "nein"},
        )
        self.assertTrue(SchoolClass.objects.filter(pk=self.school_class.pk).exists())

    def test_delete_with_confirmation(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("schools:class_delete", args=[self.school_class.pk]),
            {"confirm": "löschen"},
        )
        self.assertFalse(SchoolClass.objects.filter(pk=self.school_class.pk).exists())

    def test_collaborator_cannot_delete_class(self):
        colleague = make_teacher("delcol@example.com", school=self.owner.school)
        ClassMembership.objects.create(
            school_class=self.school_class,
            teacher=colleague,
            role=ClassMembership.Role.COLLABORATOR,
        )
        self.client.force_login(colleague)
        response = self.client.post(
            reverse("schools:class_delete", args=[self.school_class.pk]),
            {"confirm": "löschen"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SchoolClass.objects.filter(pk=self.school_class.pk).exists())


class StudentImportTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("imp@example.com")
        self.school_class = make_class(self.teacher)
        self.client.force_login(self.teacher)

    def test_import_two_columns(self):
        self.client.post(
            reverse("schools:student_import", args=[self.school_class.pk]),
            {"data": "7b-001\ta1b2c3\n7b-002\td4e5f6"},
        )
        codes = set(self.school_class.students.values_list("access_code", flat=True))
        self.assertEqual(codes, {"a1b2c3", "d4e5f6"})
        s = self.school_class.students.get(access_code="a1b2c3")
        self.assertEqual(s.display_name, "7b-001")

    def test_import_single_column_and_normalise(self):
        self.client.post(
            reverse("schools:student_import", args=[self.school_class.pk]),
            {"data": " ABC123 \nXYZ789"},
        )
        codes = set(self.school_class.students.values_list("access_code", flat=True))
        self.assertEqual(codes, {"abc123", "xyz789"})  # lowercased, trimmed

    def test_import_skips_existing_token(self):
        Student.objects.create(school_class=self.school_class, access_code="dup123")
        self.client.post(
            reverse("schools:student_import", args=[self.school_class.pk]),
            {"data": "dup123\nnew123"},
        )
        self.assertTrue(self.school_class.students.filter(access_code="new123").exists())
        self.assertEqual(
            self.school_class.students.filter(access_code="dup123").count(), 1
        )

    def test_import_rejects_invalid_token(self):
        self.client.post(
            reverse("schools:student_import", args=[self.school_class.pk]),
            {"data": "name\tok!!"},
        )
        self.assertFalse(self.school_class.students.exists())

    def test_set_token(self):
        s = Student.objects.create(school_class=self.school_class)
        self.client.post(
            reverse("schools:student_set_token", args=[self.school_class.pk, s.pk]),
            {"token": "Mein-Code"},  # normalised -> invalid (hyphen) -> unchanged
        )
        s.refresh_from_db()
        self.assertNotEqual(s.access_code, "mein-code")
        # valid token
        self.client.post(
            reverse("schools:student_set_token", args=[self.school_class.pk, s.pk]),
            {"token": "GOOD99"},
        )
        s.refresh_from_db()
        self.assertEqual(s.access_code, "good99")

    def test_set_token_rejects_duplicate(self):
        a = Student.objects.create(school_class=self.school_class, access_code="aaa111")
        b = Student.objects.create(school_class=self.school_class)
        self.client.post(
            reverse("schools:student_set_token", args=[self.school_class.pk, b.pk]),
            {"token": "aaa111"},
        )
        b.refresh_from_db()
        self.assertNotEqual(b.access_code, "aaa111")
