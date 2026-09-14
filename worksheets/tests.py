import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from schools.models import ClassMembership, School, SchoolClass, Student

from .models import Assignment, AssignmentFile

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def make_teacher(email, school=None):
    return User.objects.create_user(
        email=email, password="pw-strong-123", first_name="T", last_name="L", school=school
    )


def make_class(teacher, name="8a"):
    school = teacher.school or School.objects.create(name="Testschule")
    if teacher.school_id != school.id:
        teacher.school = school
        teacher.save(update_fields=["school"])
    sc = SchoolClass.objects.create(school=school, name=name, subject="Info")
    ClassMembership.objects.create(
        school_class=sc, teacher=teacher, role=ClassMembership.Role.OWNER
    )
    return sc


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class WorksheetTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.teacher = make_teacher("t@example.com")
        self.school_class = make_class(self.teacher)
        self.student = Student.objects.create(
            school_class=self.school_class, display_name="Anna"
        )

    def _upload(self):
        return SimpleUploadedFile(
            "arbeitsblatt.pdf", b"%PDF-1.4 inhalt", content_type="application/pdf"
        )

    def test_teacher_creates_assignment_with_file(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("worksheets:assignment_create", args=[self.school_class.pk]),
            {"title": "Arbeitsblatt 1", "description": "Bitte lösen", "files": self._upload()},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        assignment = Assignment.objects.get(title="Arbeitsblatt 1")
        self.assertEqual(assignment.school_class, self.school_class)
        self.assertEqual(assignment.files.count(), 1)
        self.assertEqual(assignment.files.first().original_name, "arbeitsblatt.pdf")

    def test_teacher_pages_render(self):
        self.client.force_login(self.teacher)
        # Create form
        r = self.client.get(
            reverse("worksheets:assignment_create", args=[self.school_class.pk])
        )
        self.assertEqual(r.status_code, 200)
        # Detail + edit
        assignment, _ = self._make_assignment_with_file()
        self.assertEqual(
            self.client.get(assignment.get_absolute_url()).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("worksheets:assignment_edit", args=[assignment.pk])
            ).status_code,
            200,
        )

    def test_non_member_teacher_cannot_create(self):
        other = make_teacher("other@example.com")
        self.client.force_login(other)
        response = self.client.post(
            reverse("worksheets:assignment_create", args=[self.school_class.pk]),
            {"title": "X"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Assignment.objects.filter(title="X").exists())

    def _make_assignment_with_file(self):
        assignment = Assignment.objects.create(
            school_class=self.school_class, title="AB", created_by=self.teacher
        )
        af = AssignmentFile.objects.create(assignment=assignment, file=self._upload())
        return assignment, af

    def test_student_sees_assignment_on_home(self):
        self._make_assignment_with_file()
        response = self.client.get(
            reverse("schools:student_space", args=[self.student.access_code])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AB")
        self.assertContains(response, "arbeitsblatt.pdf")

    def test_student_can_download_file(self):
        _, af = self._make_assignment_with_file()
        # Establish the student session via the token URL first.
        self.client.get(reverse("schools:student_space", args=[self.student.access_code]))
        response = self.client.get(reverse("worksheets:file_download", args=[af.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 inhalt")

    def test_teacher_can_download_file(self):
        _, af = self._make_assignment_with_file()
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("worksheets:file_download", args=[af.pk]))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_download_file(self):
        _, af = self._make_assignment_with_file()
        response = self.client.get(reverse("worksheets:file_download", args=[af.pk]))
        self.assertEqual(response.status_code, 404)

    def test_student_of_other_class_cannot_download(self):
        _, af = self._make_assignment_with_file()
        other_class = make_class(make_teacher("t2@example.com"), name="9b")
        other_student = Student.objects.create(school_class=other_class)
        self.client.get(
            reverse("schools:student_space", args=[other_student.access_code])
        )
        response = self.client.get(reverse("worksheets:file_download", args=[af.pk]))
        self.assertEqual(response.status_code, 404)

    def test_delete_assignment_removes_files(self):
        assignment, af = self._make_assignment_with_file()
        path = af.file.path
        import os

        self.assertTrue(os.path.exists(path))
        self.client.force_login(self.teacher)
        self.client.post(reverse("worksheets:assignment_delete", args=[assignment.pk]))
        self.assertFalse(Assignment.objects.filter(pk=assignment.pk).exists())
        self.assertFalse(os.path.exists(path))
