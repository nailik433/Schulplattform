import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from schools.models import ClassMembership, School, SchoolClass, Student

from .models import ApiKey, Lesson, LessonResult

User = get_user_model()


def make_teacher(email, school=None):
    return User.objects.create_user(
        email=email, password="pw-strong-123", first_name="T", last_name="L", school=school
    )


def make_class(teacher, name="7b"):
    school = teacher.school or School.objects.create(name="Testschule")
    if teacher.school_id != school.id:
        teacher.school = school
        teacher.save(update_fields=["school"])
    sc = SchoolClass.objects.create(school=school, name=name, subject="Info")
    ClassMembership.objects.create(school_class=sc, teacher=teacher, role=ClassMembership.Role.OWNER)
    return sc


HTML = "<!DOCTYPE html><html><body><h1>Magnetismus</h1></body></html>"


class TeacherLessonTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("t@example.com")
        self.sc = make_class(self.teacher)
        self.client.force_login(self.teacher)

    def test_create_and_detail(self):
        r = self.client.post(
            reverse("lessons:lesson_create", args=[self.sc.pk]),
            {"title": "Magnetismus", "html": HTML},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        lesson = Lesson.objects.get(title="Magnetismus")
        self.assertEqual(lesson.school_class, self.sc)
        self.assertContains(self.client.get(lesson.get_absolute_url()), "Magnetismus")

    def test_preview_served_isolated(self):
        lesson = Lesson.objects.create(school_class=self.sc, title="X", html=HTML)
        r = self.client.get(reverse("lessons:lesson_preview", args=[lesson.pk]))
        self.assertContains(r, "Magnetismus")
        # Our own pages may embed it; a DENY header would blank the iframe.
        self.assertEqual(r["X-Frame-Options"], "SAMEORIGIN")
        # Opened directly in a tab it still runs with an opaque origin, so it
        # can never act as the logged-in teacher.
        self.assertIn("sandbox", r["Content-Security-Policy"])
        self.assertNotIn("allow-same-origin", r["Content-Security-Policy"])

    def test_non_member_cannot_create(self):
        other = make_teacher("o@example.com")
        self.client.force_login(other)
        r = self.client.post(
            reverse("lessons:lesson_create", args=[self.sc.pk]),
            {"title": "X", "html": HTML},
        )
        self.assertEqual(r.status_code, 404)

    def test_delete(self):
        lesson = Lesson.objects.create(school_class=self.sc, title="X", html=HTML)
        self.client.post(reverse("lessons:lesson_delete", args=[lesson.pk]))
        self.assertFalse(Lesson.objects.filter(pk=lesson.pk).exists())


class StudentLessonTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("t2@example.com")
        self.sc = make_class(self.teacher)
        self.lesson = Lesson.objects.create(school_class=self.sc, title="X", html=HTML)
        self.student = Student.objects.create(school_class=self.sc)

    def _session(self):
        self.client.get(reverse("schools:student_space", args=[self.student.access_code]))

    def test_play_requires_session(self):
        r = self.client.get(reverse("lessons:lesson_play", args=[self.lesson.pk]))
        self.assertRedirects(r, reverse("schools:student_login"))

    def test_play_and_content(self):
        self._session()
        play = self.client.get(reverse("lessons:lesson_play", args=[self.lesson.pk]))
        self.assertEqual(play.status_code, 200)
        self.assertContains(play, "X-CSRFToken")  # result bridge sends the token
        content = self.client.get(reverse("lessons:lesson_content", args=[self.lesson.pk]))
        self.assertContains(content, "Magnetismus")
        self.assertEqual(content["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("sandbox", content["Content-Security-Policy"])

    def test_report_requires_csrf_token(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        strict.get(reverse("schools:student_space", args=[self.student.access_code]))
        r = strict.post(
            reverse("lessons:lesson_report", args=[self.lesson.pk]),
            data=json.dumps({"score": 1, "max": 1}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)
        self.assertFalse(
            LessonResult.objects.filter(lesson=self.lesson, student=self.student, completed=True).exists()
        )

    def test_report_result(self):
        self._session()
        self.client.post(
            reverse("lessons:lesson_report", args=[self.lesson.pk]),
            data=json.dumps({"score": 8, "max": 10, "completed": True}),
            content_type="application/json",
        )
        res = LessonResult.objects.get(lesson=self.lesson, student=self.student)
        self.assertEqual(res.score, 8)
        self.assertEqual(res.max_score, 10)
        self.assertTrue(res.completed)
        self.assertEqual(res.percent, 80)

    def test_student_of_other_class_cannot_play(self):
        other_class = make_class(make_teacher("t3@example.com"), name="9z")
        other_student = Student.objects.create(school_class=other_class)
        self.client.get(reverse("schools:student_space", args=[other_student.access_code]))
        self.assertEqual(self.client.get(reverse("lessons:lesson_play", args=[self.lesson.pk])).status_code, 404)


class ApiTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("api@example.com")
        self.sc = make_class(self.teacher)
        self.key = ApiKey.objects.create(teacher=self.teacher).key

    def test_requires_key(self):
        self.assertEqual(self.client.get("/api/classes").status_code, 401)

    def test_list_classes(self):
        r = self.client.get("/api/classes", HTTP_X_API_KEY=self.key)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["classes"][0]["id"], self.sc.id)

    def test_create_lesson(self):
        r = self.client.post(
            "/api/lessons",
            data=json.dumps({"class_id": self.sc.id, "title": "KI-Stunde", "html": HTML}),
            content_type="application/json",
            HTTP_X_API_KEY=self.key,
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Lesson.objects.filter(title="KI-Stunde", school_class=self.sc).exists())

    def test_create_rejects_foreign_class(self):
        other = make_class(make_teacher("x@example.com"), name="5a")
        r = self.client.post(
            "/api/lessons",
            data=json.dumps({"class_id": other.id, "title": "Nope", "html": HTML}),
            content_type="application/json",
            HTTP_X_API_KEY=self.key,
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Lesson.objects.filter(title="Nope").exists())

    def test_create_requires_html_and_title(self):
        r = self.client.post(
            "/api/lessons",
            data=json.dumps({"class_id": self.sc.id, "title": "", "html": ""}),
            content_type="application/json",
            HTTP_X_API_KEY=self.key,
        )
        self.assertEqual(r.status_code, 400)


class ApiKeyPageTests(TestCase):
    def test_page_shows_key_and_prompt(self):
        teacher = make_teacher("kp@example.com")
        self.client.force_login(teacher)
        r = self.client.get(reverse("lessons:api_key"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(teacher.api_keys.filter(is_active=True).exists())
        self.assertContains(r, "lesson_result")  # the prompt is present
