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


class ApiLessonListTests(TestCase):
    def test_list_lessons_for_class(self):
        teacher = make_teacher("list@example.com")
        sc = make_class(teacher)
        key = ApiKey.objects.create(teacher=teacher).key
        Lesson.objects.create(school_class=sc, title="Erste", html=HTML)
        r = self.client.get(f"/api/lessons?class_id={sc.id}", HTTP_X_API_KEY=key)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([l["title"] for l in r.json()["lessons"]], ["Erste"])
        self.assertIn("/lernumgebung/", r.json()["lessons"][0]["teacher_url"])
        other = make_class(make_teacher("y@example.com"), name="6c")
        self.assertEqual(self.client.get(f"/api/lessons?class_id={other.id}", HTTP_X_API_KEY=key).status_code, 400)


class McpEndpointTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher("mcp@example.com")
        self.sc = make_class(self.teacher, name="R7a")
        self.key = ApiKey.objects.create(teacher=self.teacher).key

    def _rpc(self, method, params=None, msg_id=1, path="/mcp", bearer=True):
        body = {"jsonrpc": "2.0", "method": method}
        if msg_id is not None:
            body["id"] = msg_id
        if params is not None:
            body["params"] = params
        extra = {"HTTP_AUTHORIZATION": f"Bearer {self.key}"} if bearer else {}
        return self.client.post(path, data=json.dumps(body), content_type="application/json", **extra)

    def test_requires_key(self):
        r = self._rpc("tools/list", bearer=False)
        self.assertEqual(r.status_code, 401)
        self.assertIn("Bearer", r["WWW-Authenticate"])

    def test_initialize_negotiates_protocol(self):
        r = self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
        data = r.json()
        self.assertEqual(data["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(data["result"]["serverInfo"]["name"], "schulplattform")
        self.assertIn("tools", data["result"]["capabilities"])
        # Unknown versions fall back to the latest we support.
        r2 = self._rpc("initialize", {"protocolVersion": "1999-01-01"})
        self.assertEqual(r2.json()["result"]["protocolVersion"], "2025-06-18")

    def test_notification_is_acknowledged_without_body(self):
        r = self._rpc("notifications/initialized", msg_id=None)
        self.assertEqual(r.status_code, 202)

    def test_tools_list(self):
        names = [t["name"] for t in self._rpc("tools/list").json()["result"]["tools"]]
        self.assertEqual(
            names,
            ["klassen_auflisten", "lernumgebungen_auflisten", "lernumgebung_anlegen", "lernumgebung_aktualisieren"],
        )

    def test_call_list_classes_and_create_lesson(self):
        r = self._rpc("tools/call", {"name": "klassen_auflisten", "arguments": {}})
        text = r.json()["result"]["content"][0]["text"]
        self.assertIn(f"ID {self.sc.id}: R7a", text)

        r = self._rpc("tools/call", {"name": "lernumgebung_anlegen",
                                     "arguments": {"klasse_id": self.sc.id, "titel": "Bit-Labor", "html": HTML}})
        result = r.json()["result"]
        self.assertFalse(result.get("isError"))
        lesson = Lesson.objects.get(title="Bit-Labor", school_class=self.sc)
        self.assertIn(f"/lernumgebung/{lesson.pk}/", result["content"][0]["text"])

        r = self._rpc("tools/call", {"name": "lernumgebungen_auflisten", "arguments": {"klasse_id": self.sc.id}})
        self.assertIn("Bit-Labor", r.json()["result"]["content"][0]["text"])

        r = self._rpc("tools/call", {"name": "lernumgebung_aktualisieren",
                                     "arguments": {"lernumgebung_id": lesson.pk, "titel": "Bit-Labor v2", "html": HTML}})
        lesson.refresh_from_db()
        self.assertEqual(lesson.title, "Bit-Labor v2")

    def test_foreign_class_is_a_tool_error_not_a_crash(self):
        other = make_class(make_teacher("z@example.com"), name="5a")
        r = self._rpc("tools/call", {"name": "lernumgebung_anlegen",
                                     "arguments": {"klasse_id": other.id, "titel": "Nope", "html": HTML}})
        self.assertTrue(r.json()["result"]["isError"])
        self.assertFalse(Lesson.objects.filter(title="Nope").exists())

    def test_key_in_path_for_clients_without_headers(self):
        r = self._rpc("tools/list", path=f"/mcp/{self.key}/", bearer=False)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._rpc("tools/list", path="/mcp/sk_falsch/", bearer=False).status_code, 401)

    def test_unknown_method_and_parse_error(self):
        self.assertEqual(self._rpc("does/not/exist").json()["error"]["code"], -32601)
        r = self.client.post("/mcp", data="nicht json", content_type="application/json",
                             HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(r.status_code, 400)

    def test_get_is_not_supported(self):
        self.assertEqual(self.client.get("/mcp", HTTP_AUTHORIZATION=f"Bearer {self.key}").status_code, 405)


# ==========================================================================
# Zwischenstand (work-in-progress per pupil) + Zusatzpunkte
# ==========================================================================

import pathlib  # noqa: E402

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402

from .models import LessonState  # noqa: E402
from .protocol import LESSON_PROTOCOL  # noqa: E402
from .views import STATE_MAX_BYTES  # noqa: E402


class StateTestBase(TestCase):
    def setUp(self):
        self.teacher = make_teacher("zs@example.com")
        self.sc = make_class(self.teacher)
        self.lesson = Lesson.objects.create(school_class=self.sc, title="Mit Stand", html=HTML)
        self.anna = Student.objects.create(school_class=self.sc, display_name="Anna")
        self.ben = Student.objects.create(school_class=self.sc, display_name="Ben")
        self.save_url = reverse("lessons:lesson_state", args=[self.lesson.pk])
        self.play_url = reverse("lessons:lesson_play", args=[self.lesson.pk])

    def login_as(self, student, client=None):
        client = client or self.client
        client.get(reverse("schools:student_space", args=[student.access_code]))
        return client

    def save(self, state, client=None, **kwargs):
        return (client or self.client).post(
            self.save_url, data=json.dumps({"state": state}), content_type="application/json", **kwargs
        )


class LessonStateApiTests(StateTestBase):
    def test_pupil_saves_and_gets_the_state_back_when_reopening(self):
        self.login_as(self.anna)
        r = self.save({"count": 3, "note": "Übung ä ö ü"})
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True}))
        self.assertEqual(LessonState.objects.get().student, self.anna)

        # "close the tab, open it again": a fresh page load delivers the saved state
        page = self.client.get(self.play_url)
        self.assertEqual(page.context["initial_state"], {"count": 3, "note": "Übung ä ö ü"})
        self.assertContains(page, 'id="lesson-initial-state"')

    def test_first_visit_has_no_state(self):
        self.login_as(self.anna)
        page = self.client.get(self.play_url)
        self.assertIsNone(page.context["initial_state"])
        self.assertContains(page, '<script id="lesson-initial-state" type="application/json">null</script>')

    def test_second_save_replaces_the_first_one(self):
        self.login_as(self.anna)
        self.save({"v": 1})
        self.save({"v": 2})
        self.assertEqual(LessonState.objects.count(), 1)
        self.assertEqual(LessonState.objects.get().state, {"v": 2})

    def test_another_pupil_on_the_same_device_does_not_see_it(self):
        self.login_as(self.anna)
        self.save({"geheim": "annas antwort"})
        # shared iPad: Anna logs out, Ben logs in on the same browser
        self.client.get(reverse("schools:student_logout"))
        self.login_as(self.ben)
        page = self.client.get(self.play_url)
        self.assertIsNone(page.context["initial_state"])
        self.assertNotContains(page, "annas antwort")
        self.save({"geheim": "bens antwort"})
        self.assertEqual(LessonState.objects.count(), 2)
        # and Anna still gets her own
        self.client.get(reverse("schools:student_logout"))
        self.login_as(self.anna)
        self.assertEqual(self.client.get(self.play_url).context["initial_state"], {"geheim": "annas antwort"})

    def test_pupil_cannot_write_someone_elses_state(self):
        # the pupil comes from the session; a "student" field in the body is ignored
        self.login_as(self.ben)
        self.client.post(
            self.save_url,
            data=json.dumps({"state": {"x": 1}, "student": self.anna.pk, "student_id": self.anna.pk}),
            content_type="application/json",
        )
        self.assertEqual(list(LessonState.objects.values_list("student", flat=True)), [self.ben.pk])

    def test_only_logged_in_pupils_of_that_class(self):
        # not logged in
        self.assertEqual(self.save({"x": 1}).status_code, 404)
        # a teacher is not a pupil
        self.client.force_login(self.teacher)
        self.assertEqual(self.save({"x": 1}).status_code, 404)
        self.client.logout()
        # pupil of a different class
        other_class = make_class(make_teacher("anderer@example.com"), name="9z")
        stranger = Student.objects.create(school_class=other_class)
        self.login_as(stranger)
        self.assertEqual(self.save({"x": 1}).status_code, 404)
        self.assertFalse(LessonState.objects.exists())

    def test_deactivated_pupil_cannot_save(self):
        self.login_as(self.anna)
        self.anna.is_active = False
        self.anna.save(update_fields=["is_active"])
        self.assertEqual(self.save({"x": 1}).status_code, 404)

    def test_size_limit_is_64_kb_of_compact_json(self):
        self.login_as(self.anna)
        overhead = len('{"a":""}')
        ok = self.save({"a": "x" * (STATE_MAX_BYTES - overhead)})  # exactly 65536 bytes
        self.assertEqual(ok.status_code, 200)
        too_big = self.save({"a": "x" * (STATE_MAX_BYTES - overhead + 1)})
        self.assertEqual((too_big.status_code, too_big.json()["error"]), (413, "too_large"))
        # multi-byte characters count as bytes, not characters
        umlauts = self.save({"a": "ä" * (STATE_MAX_BYTES // 2)})
        self.assertEqual(umlauts.status_code, 413)
        self.assertEqual(LessonState.objects.get().state["a"], "x" * (STATE_MAX_BYTES - overhead))  # unchanged

    def test_huge_request_is_refused_before_it_is_read(self):
        self.login_as(self.anna)
        r = self.client.post(
            self.save_url, data='{"state":"' + "x" * 200_000 + '"}', content_type="application/json"
        )
        self.assertEqual(r.status_code, 413)

    def test_invalid_bodies_are_rejected_not_crashed_on(self):
        self.login_as(self.anna)
        for body in ("nicht json", "[]", '{"kein_state": 1}', '{"state": NaN}', '{"state": Infinity}', "[" * 5000):
            r = self.client.post(self.save_url, data=body, content_type="application/json")
            self.assertEqual(r.status_code, 400, body[:20])
        self.assertFalse(LessonState.objects.exists())

    def test_any_json_type_is_allowed(self):
        self.login_as(self.anna)
        for value in ([1, 2, 3], {"a": [{"b": None}]}, "text", 42, True, 0, "", {}):
            self.assertEqual(self.save(value).status_code, 200, repr(value))
            self.assertEqual(LessonState.objects.get().state, value)

    def test_null_deletes_the_state(self):
        self.login_as(self.anna)
        self.save({"x": 1})
        self.assertEqual(self.save(None).status_code, 200)
        self.assertFalse(LessonState.objects.exists())
        self.assertEqual(self.save(None).status_code, 200)  # idempotent

    def test_csrf_token_is_required(self):
        strict = Client(enforce_csrf_checks=True)
        strict.get(reverse("schools:student_space", args=[self.anna.access_code]))
        r = strict.post(self.save_url, data=json.dumps({"state": {"x": 1}}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(LessonState.objects.exists())

    def test_get_is_not_allowed(self):
        self.login_as(self.anna)
        self.assertEqual(self.client.get(self.save_url).status_code, 405)

    def test_state_is_deleted_with_the_pupil(self):
        self.login_as(self.anna)
        self.save({"x": 1})
        self.anna.delete()
        self.assertFalse(LessonState.objects.exists())

    def test_play_page_is_never_cached(self):
        self.login_as(self.anna)
        cache_control = self.client.get(self.play_url)["Cache-Control"]
        self.assertIn("no-store", cache_control)


class LessonStateParentPageTests(StateTestBase):
    def test_listener_is_registered_before_the_iframe_loads(self):
        self.login_as(self.anna)
        html = self.client.get(self.play_url).content.decode()
        self.assertLess(html.index("addEventListener('message'"), html.index("<iframe"))
        self.assertLess(html.index('id="lesson-initial-state"'), html.index("<iframe"))

    def test_page_speaks_the_whole_protocol_and_checks_the_sender(self):
        self.login_as(self.anna)
        html = self.client.get(self.play_url).content.decode()
        for marker in ("lesson_state_request", "lesson_state_save", "lesson_state_saved",
                       "'lesson_state'", "e.source !== frameWindow()", "pagehide", "X-CSRFToken",
                       "extra_max", "DEBOUNCE_MS"):
            self.assertIn(marker, html, marker)

    def test_state_with_script_tags_cannot_break_out_of_the_page(self):
        self.login_as(self.anna)
        self.save({"note": "</script><script>alert(1)</script>"})
        html = self.client.get(self.play_url).content.decode()
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertIn("\\u003C/script\\u003E", html)  # json_script escapes it

    def test_teacher_preview_answers_with_no_state_and_stores_nothing(self):
        self.client.force_login(self.teacher)
        html = self.client.get(self.lesson.get_absolute_url()).content.decode()
        self.assertIn("lesson_state_request", html)
        self.assertIn("state: null", html)
        self.assertNotIn("lesson_state_save", html)
        self.assertFalse(LessonState.objects.exists())


class LessonStateResetTests(StateTestBase):
    def setUp(self):
        super().setUp()
        LessonState.objects.create(lesson=self.lesson, student=self.anna, state={"a": 1})
        LessonState.objects.create(lesson=self.lesson, student=self.ben, state={"b": 2})
        self.client.force_login(self.teacher)

    def test_detail_page_lists_saved_states_with_reset_buttons(self):
        r = self.client.get(self.lesson.get_absolute_url())
        self.assertEqual(r.context["state_count"], 2)
        self.assertContains(r, "Zwischenstand")
        self.assertContains(r, "Fortschritt für alle zurücksetzen")
        self.assertContains(r, reverse("lessons:state_reset", args=[self.lesson.pk, self.anna.pk]))

    def test_reset_one_pupil(self):
        r = self.client.post(reverse("lessons:state_reset", args=[self.lesson.pk, self.anna.pk]), follow=True)
        self.assertContains(r, "zurückgesetzt")
        self.assertEqual(list(LessonState.objects.values_list("student", flat=True)), [self.ben.pk])

    def test_reset_keeps_the_points_already_reported(self):
        LessonResult.objects.create(lesson=self.lesson, student=self.anna, score=3, max_score=5, completed=True)
        self.client.post(reverse("lessons:state_reset", args=[self.lesson.pk, self.anna.pk]))
        self.assertEqual(LessonResult.objects.get(student=self.anna).score, 3)

    def test_reset_all(self):
        self.client.post(reverse("lessons:state_reset_all", args=[self.lesson.pk]))
        self.assertFalse(LessonState.objects.exists())

    def test_reset_needs_post_and_membership(self):
        url = reverse("lessons:state_reset", args=[self.lesson.pk, self.anna.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        stranger = make_teacher("fremd@example.com")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.post(reverse("lessons:state_reset_all", args=[self.lesson.pk])).status_code, 404)
        self.assertEqual(LessonState.objects.count(), 2)

    def test_cannot_reset_a_pupil_from_another_class(self):
        other_class = make_class(self.teacher, name="8x")
        stranger = Student.objects.create(school_class=other_class)
        LessonState.objects.create(lesson=self.lesson, student=stranger, state={})  # impossible in practice
        r = self.client.post(reverse("lessons:state_reset", args=[self.lesson.pk, stranger.pk]))
        self.assertEqual(r.status_code, 404)

    def test_pupil_reopens_after_reset_and_starts_fresh(self):
        self.client.logout()
        self.login_as(self.anna)
        self.assertEqual(self.client.get(self.play_url).context["initial_state"], {"a": 1})
        self.client.logout()
        self.client.force_login(self.teacher)
        self.client.post(reverse("lessons:state_reset", args=[self.lesson.pk, self.anna.pk]))
        self.client.logout()
        self.login_as(self.anna)
        self.assertIsNone(self.client.get(self.play_url).context["initial_state"])


class ExtraPointsTests(StateTestBase):
    def report(self, payload):
        return self.client.post(
            reverse("lessons:lesson_report", args=[self.lesson.pk]),
            data=payload if isinstance(payload, str) else json.dumps(payload),
            content_type="application/json",
        )

    def test_extra_points_are_stored(self):
        self.login_as(self.anna)
        self.report({"score": 8, "max": 10, "extra": 2, "extra_max": 3, "completed": True})
        res = LessonResult.objects.get(student=self.anna)
        self.assertEqual((res.score, res.max_score, res.extra, res.extra_max), (8, 10, 2, 3))
        self.assertEqual(res.percent, 80)  # extra points never distort the main percentage

    def test_without_extra_nothing_changes(self):
        self.login_as(self.anna)
        self.report({"score": 5, "max": 5})
        res = LessonResult.objects.get(student=self.anna)
        self.assertIsNone(res.extra)
        self.assertIsNone(res.extra_max)

    def test_a_later_report_without_extra_keeps_the_earlier_extra(self):
        self.login_as(self.anna)
        self.report({"score": 5, "max": 5, "extra": 1, "extra_max": 2})
        self.report({"score": 5, "max": 5})
        self.assertEqual(LessonResult.objects.get().extra, 1)

    def test_garbage_numbers_are_ignored(self):
        self.login_as(self.anna)
        self.report({"score": True, "max": "10", "extra": "viel", "extra_max": None})
        self.report('{"score": NaN, "max": Infinity, "extra": -Infinity}')
        res = LessonResult.objects.get(student=self.anna)
        for value in (res.score, res.max_score, res.extra, res.extra_max):
            self.assertIsNone(value)

    def test_teacher_sees_extra_points(self):
        self.login_as(self.anna)
        self.report({"score": 4, "max": 5, "extra": 2, "extra_max": 3, "completed": True})
        self.client.logout()
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(self.lesson.get_absolute_url()), "+2 / 3 Zusatz")


class ProtocolDocumentationTests(TestCase):
    def test_mcp_server_instructions_describe_the_protocol(self):
        teacher = make_teacher("doc@example.com")
        key = ApiKey.objects.create(teacher=teacher).key
        r = self.client.post(
            "/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {key}",
        )
        instructions = r.json()["result"]["instructions"]
        for marker in ("lesson_state_request", "lesson_state_save", "lesson_state", "localStorage",
                       "extra_max", "64 KB", "PlatformState"):
            self.assertIn(marker, instructions, marker)
        self.assertEqual(instructions.count("SCHNITTSTELLE ZUR PLATTFORM"), 1)

    def test_api_page_prompt_contains_the_protocol(self):
        teacher = make_teacher("doc2@example.com")
        self.client.force_login(teacher)
        r = self.client.get(reverse("lessons:api_key"))
        self.assertContains(r, "lesson_state_request")
        self.assertContains(r, "lesson_state_save")

    def test_example_lesson_in_docs_uses_the_protocol(self):
        example = pathlib.Path(settings.BASE_DIR, "docs", "beispiel-zwischenstand.html").read_text()
        for marker in ("lesson_state_request", "lesson_state_save", "e.source === parent", "extra_max"):
            self.assertIn(marker, example, marker)
        self.assertNotIn("localStorage", example)

    def test_protocol_text_has_no_stale_leftovers(self):
        self.assertNotIn("TODO", LESSON_PROTOCOL)


class TemplateHygieneTests(TestCase):
    def test_no_template_comment_leaks_into_the_page(self):
        """Django's {# #} only works on a single line; a multi-line one is printed
        verbatim into the page (this happened once on the player page)."""
        root = pathlib.Path(settings.BASE_DIR, "templates")
        for path in root.rglob("*.html"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if "{#" in line:
                    self.assertIn("#}", line, f"{path.relative_to(root)}:{number} mehrzeiliger {{# #}}-Kommentar")

    def test_player_page_shows_no_template_source(self):
        teacher = make_teacher("hy@example.com")
        sc = make_class(teacher)
        lesson = Lesson.objects.create(school_class=sc, title="X", html=HTML)
        student = Student.objects.create(school_class=sc)
        self.client.get(reverse("schools:student_space", args=[student.access_code]))
        html = self.client.get(reverse("lessons:lesson_play", args=[lesson.pk])).content.decode()
        for leak in ("{#", "#}", "{%", "%}", "{{", "}}"):
            self.assertNotIn(leak, html, leak)
