import os
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from lessons.models import Lesson, LessonResult
from materials.models import MaterialFile
from schools.models import ClassMembership, School, SchoolClass, Student
from worksheets.models import Assignment, AssignmentFile, Submission, SubmissionFile

from .models import ClassProject, Project, ProjectItem
from .services import instantiate_project

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()
HTML = "<!DOCTYPE html><html><body><h1>Bit-Labor</h1></body></html>"


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


def pdf(name="blatt.pdf", content=b"%PDF-1.4 inhalt"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProjectTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.teacher = make_teacher("p@example.com")
        self.sc = make_class(self.teacher, "7b")
        self.sc2 = make_class(self.teacher, "7c")
        self.client.force_login(self.teacher)
        self.project = Project.objects.create(owner=self.teacher, title="Bit & Byte", description="Zahlensysteme")

    def full_project(self):
        """Lesson + worksheet (with a material file) + task, in this order."""
        self.material = MaterialFile.objects.create(owner=self.teacher, file=pdf("zahlen.pdf", b"ZAHLEN"))
        ProjectItem.objects.create(project=self.project, kind="lesson", position=1, title="Bit-Labor", html=HTML)
        ws = ProjectItem.objects.create(
            project=self.project, kind="worksheet", position=2, title="Arbeitsblatt 1", description="Löse 1-4."
        )
        ws.material_files.add(self.material)
        ProjectItem.objects.create(
            project=self.project, kind="task", position=3, title="Präsentation", description="Erstelle eine Präsentation."
        )
        return self.project


class ProjectAccessTests(ProjectTestBase):
    def test_other_teacher_cannot_see_or_change_my_project(self):
        other = make_teacher("o@example.com")
        item = ProjectItem.objects.create(project=self.project, kind="task", title="T", description="x", position=1)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:edit", args=[self.project.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("projects:delete", args=[self.project.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:item_edit", args=[item.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:apply", args=[self.project.pk])).status_code, 404)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        # the list only shows own projects
        self.assertNotContains(self.client.get(reverse("projects:list")), "Bit &amp; Byte")

    def test_create_edit_delete_project(self):
        r = self.client.post(reverse("projects:create"), {"title": "Neu", "description": "d"}, follow=True)
        project = Project.objects.get(title="Neu")
        self.assertEqual(project.owner, self.teacher)
        self.assertContains(r, "Neu")
        self.client.post(reverse("projects:edit", args=[project.pk]), {"title": "Umbenannt", "description": ""})
        project.refresh_from_db()
        self.assertEqual(project.title, "Umbenannt")
        self.client.post(reverse("projects:delete", args=[project.pk]))
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_pages_render(self):
        self.full_project()
        for name, args in (
            ("projects:list", []),
            ("projects:create", []),
            ("projects:detail", [self.project.pk]),
            ("projects:edit", [self.project.pk]),
            ("projects:apply", [self.project.pk]),
            ("projects:class_apply", [self.sc.pk]),
        ):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        for kind in ("lesson", "worksheet", "task"):
            self.assertEqual(
                self.client.get(reverse("projects:item_create", args=[self.project.pk, kind])).status_code, 200, kind
            )
        self.assertEqual(self.client.get(reverse("projects:item_create", args=[self.project.pk, "unfug"])).status_code, 404)


class BuildingBlockTests(ProjectTestBase):
    def _create(self, kind, data):
        return self.client.post(reverse("projects:item_create", args=[self.project.pk, kind]), data)

    def test_lesson_needs_html_or_a_source_lesson(self):
        r = self._create("lesson", {"title": "Leer", "html": ""})
        self.assertContains(r, "Bitte HTML einfügen")
        self.assertFalse(self.project.items.exists())
        self._create("lesson", {"title": "Direkt", "html": HTML})
        source = Lesson.objects.create(school_class=self.sc, title="Quelle", html="<p>kopiert</p>")
        self._create("lesson", {"title": "Kopie", "html": "", "copy_from_lesson": source.pk})
        self.assertEqual(self.project.items.get(title="Kopie").html, "<p>kopiert</p>")
        self.assertEqual(self.project.items.get(title="Direkt").html, HTML)

    def test_cannot_copy_from_a_lesson_of_another_teacher(self):
        other = make_teacher("fremd@example.com")
        foreign = Lesson.objects.create(school_class=make_class(other, "9z"), title="Geheim", html="<p>x</p>")
        self._create("lesson", {"title": "Dieb", "html": "", "copy_from_lesson": foreign.pk})
        self.assertFalse(self.project.items.filter(title="Dieb").exists())

    def test_worksheet_needs_a_file_from_my_material(self):
        r = self._create("worksheet", {"title": "Ohne Datei", "description": "x"})
        self.assertContains(r, "mindestens eine Datei")
        mine = MaterialFile.objects.create(owner=self.teacher, file=pdf())
        self._create("worksheet", {"title": "Mit Datei", "material_files": [mine.pk], "collect_submissions": "on"})
        item = self.project.items.get(title="Mit Datei")
        self.assertEqual(list(item.material_files.all()), [mine])
        self.assertTrue(item.collect_submissions)

    def test_worksheet_cannot_use_someone_elses_material(self):
        other = make_teacher("fremd@example.com")
        theirs = MaterialFile.objects.create(owner=other, file=pdf("fremd.pdf"))
        self._create("worksheet", {"title": "Klau", "material_files": [theirs.pk]})
        self.assertFalse(self.project.items.filter(title="Klau").exists())

    def test_task_only_asks_for_a_submission(self):
        r = self._create("task", {"title": "Präsentation", "description": ""})
        self.assertContains(r, "was die Schüler/innen abgeben")
        self._create("task", {"title": "Präsentation", "description": "Erstelle eine Präsentation."})
        item = self.project.items.get(title="Präsentation")
        self.assertEqual(item.kind, "task")
        self.assertTrue(item.collect_submissions)  # forced on, the checkbox was not even sent
        self.assertEqual(item.html, "")
        self.assertFalse(item.material_files.exists())

    def test_positions_move_and_renumber(self):
        for title in ("A", "B", "C"):
            self._create("task", {"title": title, "description": "x"})
        titles = lambda: list(self.project.items.values_list("title", flat=True))
        self.assertEqual(titles(), ["A", "B", "C"])
        c = self.project.items.get(title="C")
        self.client.post(reverse("projects:item_move", args=[c.pk, "hoch"]))
        self.assertEqual(titles(), ["A", "C", "B"])
        a = self.project.items.get(title="A")
        self.client.post(reverse("projects:item_move", args=[a.pk, "hoch"]))  # already first: no change
        self.assertEqual(titles(), ["A", "C", "B"])
        self.client.post(reverse("projects:item_move", args=[a.pk, "runter"]))
        self.assertEqual(titles(), ["C", "A", "B"])
        self.client.post(reverse("projects:item_delete", args=[a.pk]))
        self.assertEqual(titles(), ["C", "B"])
        self.assertEqual(list(self.project.items.values_list("position", flat=True)), [1, 2])
        self.assertEqual(self.client.post(reverse("projects:item_move", args=[c.pk, "quer"])).status_code, 404)

    def test_edit_item_keeps_kind_and_updates_files(self):
        m1 = MaterialFile.objects.create(owner=self.teacher, file=pdf("eins.pdf"))
        m2 = MaterialFile.objects.create(owner=self.teacher, file=pdf("zwei.pdf"))
        self._create("worksheet", {"title": "AB", "material_files": [m1.pk]})
        item = self.project.items.get()
        self.client.post(reverse("projects:item_edit", args=[item.pk]), {"title": "AB neu", "material_files": [m2.pk]})
        item.refresh_from_db()
        self.assertEqual((item.title, item.kind), ("AB neu", "worksheet"))
        self.assertEqual(list(item.material_files.all()), [m2])


class ApplyProjectTests(ProjectTestBase):
    def test_apply_copies_every_block_into_the_class(self):
        self.full_project()
        due = timezone.now() + timedelta(days=3)
        cp = instantiate_project(self.project, self.sc, self.teacher, due=due)

        self.assertEqual((cp.title, cp.school_class, cp.project), ("Bit & Byte", self.sc, self.project))
        lesson = cp.lessons.get()
        self.assertEqual((lesson.title, lesson.html, lesson.project_order), ("Bit-Labor", HTML, 1))
        ws, task = list(cp.assignments.order_by("project_order"))
        self.assertEqual((ws.title, ws.project_order, ws.description), ("Arbeitsblatt 1", 2, "Löse 1-4."))
        self.assertEqual((task.title, task.project_order), ("Präsentation", 3))
        self.assertTrue(ws.collect_submissions and task.collect_submissions)
        self.assertEqual(ws.due_date, due)
        self.assertEqual(task.due_date, due)
        self.assertEqual(ws.school_class, self.sc)
        self.assertEqual(ws.created_by, self.teacher)

    def test_deadline_only_for_blocks_that_collect_submissions(self):
        mat = MaterialFile.objects.create(owner=self.teacher, file=pdf())
        ws = ProjectItem.objects.create(project=self.project, kind="worksheet", position=1, title="Nur Material", collect_submissions=False)
        ws.material_files.add(mat)
        cp = instantiate_project(self.project, self.sc, self.teacher, due=timezone.now() + timedelta(days=1))
        a = cp.assignments.get()
        self.assertFalse(a.collect_submissions)
        self.assertIsNone(a.due_date)

    def test_files_are_copied_so_later_changes_to_the_library_do_not_matter(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        copy = AssignmentFile.objects.get(assignment__class_project=cp)
        self.assertEqual((copy.original_name, copy.file.read()), ("zahlen.pdf", b"ZAHLEN"))
        self.assertNotEqual(copy.file.path, self.material.file.path)
        self.material.file.delete(save=False)
        self.material.delete()
        copy.refresh_from_db()
        self.assertTrue(os.path.exists(copy.file.path))  # pupils still get the worksheet

    def test_template_changes_do_not_affect_classes_that_already_have_it(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        self.project.items.filter(kind="lesson").update(title="Geändert")
        self.assertEqual(cp.lessons.get().title, "Bit-Labor")

    def test_apply_view_to_several_classes(self):
        self.full_project()
        r = self.client.post(
            reverse("projects:apply", args=[self.project.pk]),
            {"classes": [self.sc.pk, self.sc2.pk], "due_date_0": "2026-11-05", "due_date_1": "14:30"},
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ClassProject.objects.count(), 2)
        for sc in (self.sc, self.sc2):
            self.assertEqual(Lesson.objects.filter(school_class=sc).count(), 1)
            self.assertEqual(Assignment.objects.filter(school_class=sc).count(), 2)
        local = timezone.localtime(Assignment.objects.first().due_date)
        self.assertEqual(local.strftime("%d.%m. %H:%M"), "05.11. 14:30")

    def test_apply_view_single_class_lands_on_the_class_project(self):
        self.full_project()
        r = self.client.post(reverse("projects:apply", args=[self.project.pk]), {"classes": [self.sc.pk]})
        cp = ClassProject.objects.get()
        self.assertRedirects(r, cp.get_absolute_url())

    def test_cannot_apply_to_a_foreign_class(self):
        self.full_project()
        foreign = make_class(make_teacher("f@example.com"), "9z")
        r = self.client.post(reverse("projects:apply", args=[self.project.pk]), {"classes": [foreign.pk]})
        self.assertEqual(r.status_code, 200)  # form error, nothing created
        self.assertFalse(ClassProject.objects.exists())
        r = self.client.get(reverse("projects:class_apply", args=[foreign.pk]))
        self.assertEqual(r.status_code, 404)

    def test_cannot_apply_an_empty_project(self):
        r = self.client.post(reverse("projects:apply", args=[self.project.pk]), {"classes": [self.sc.pk]}, follow=True)
        self.assertContains(r, "noch keine Bausteine")
        self.assertFalse(ClassProject.objects.exists())

    def test_apply_from_the_class_page(self):
        self.full_project()
        r = self.client.post(reverse("projects:class_apply", args=[self.sc.pk]), {"project": self.project.pk})
        cp = ClassProject.objects.get(school_class=self.sc)
        self.assertRedirects(r, cp.get_absolute_url())
        self.assertContains(self.client.get(self.sc.get_absolute_url()), "Bit &amp; Byte")

    def test_colleague_with_access_to_the_class_can_see_but_not_apply_my_template(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        colleague = make_teacher("kollege@example.com", school=self.teacher.school)
        ClassMembership.objects.create(school_class=self.sc, teacher=colleague, role=ClassMembership.Role.COLLABORATOR)
        self.client.force_login(colleague)
        self.assertEqual(self.client.get(cp.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("projects:class_apply", args=[self.sc.pk])).status_code, 200)
        r = self.client.post(reverse("projects:class_apply", args=[self.sc.pk]), {"project": self.project.pk})
        self.assertEqual(r.status_code, 200)  # not his project: form error


class ClassProjectLifecycleTests(ProjectTestBase):
    def test_detail_shows_progress_per_block(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        s1 = Student.objects.create(school_class=self.sc)
        Student.objects.create(school_class=self.sc)
        LessonResult.objects.create(lesson=cp.lessons.get(), student=s1, completed=True)
        Submission.objects.create(assignment=cp.assignments.get(title="Präsentation"), student=s1)
        r = self.client.get(cp.get_absolute_url())
        rows = r.context["items"]
        self.assertEqual([(row["kind"], row["done"]) for row in rows],
                         [("lesson", 1), ("assignment", 0), ("assignment", 1)])
        self.assertEqual(r.context["active"], 2)

    def test_detach_keeps_the_blocks(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        self.client.post(reverse("projects:class_detach", args=[cp.pk]))
        self.assertFalse(ClassProject.objects.filter(pk=cp.pk).exists())
        self.assertEqual(Lesson.objects.filter(school_class=self.sc, class_project=None).count(), 1)
        self.assertEqual(Assignment.objects.filter(school_class=self.sc, class_project=None).count(), 2)

    def test_delete_with_blocks_removes_submissions_and_files(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        student = Student.objects.create(school_class=self.sc)
        ws = cp.assignments.get(title="Arbeitsblatt 1")
        sub = Submission.objects.create(assignment=ws, student=student)
        sf = SubmissionFile.objects.create(submission=sub, file=pdf("loesung.pdf"))
        worksheet_blob = ws.files.get().file.path
        submission_blob = sf.file.path
        self.client.post(reverse("projects:class_delete", args=[cp.pk]))
        self.assertFalse(ClassProject.objects.exists())
        self.assertFalse(Lesson.objects.filter(school_class=self.sc).exists())
        self.assertFalse(Assignment.objects.filter(school_class=self.sc).exists())
        self.assertFalse(os.path.exists(worksheet_blob))
        self.assertFalse(os.path.exists(submission_blob))
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())  # the template survives

    def test_deleting_the_template_keeps_classes_intact(self):
        self.full_project()
        cp = instantiate_project(self.project, self.sc, self.teacher)
        self.client.post(reverse("projects:delete", args=[self.project.pk]))
        cp.refresh_from_db()
        self.assertIsNone(cp.project)
        self.assertEqual(cp.assignments.count(), 2)


class StudentProjectCardTests(ProjectTestBase):
    def setUp(self):
        super().setUp()
        self.full_project()
        self.cp = instantiate_project(self.project, self.sc, self.teacher)
        self.student = Student.objects.create(school_class=self.sc)
        # one standalone worksheet that must NOT be inside the project
        Assignment.objects.create(school_class=self.sc, title="Einzelblatt")
        self.client.logout()  # pupils have no teacher login
        self.client.get(reverse("schools:student_space", args=[self.student.access_code]))

    def _home(self):
        return self.client.get(reverse("schools:student_home"))

    def test_project_is_one_card_with_its_blocks_in_order(self):
        r = self._home()
        project = r.context["projects"][0]
        self.assertEqual(project["project"], self.cp)
        self.assertEqual([i["kind"] for i in project["items"]], ["lesson", "assignment", "assignment"])
        titles = [i["row"]["assignment"].title if i["kind"] == "assignment" else i["row"]["lesson"].title for i in project["items"]]
        self.assertEqual(titles, ["Bit-Labor", "Arbeitsblatt 1", "Präsentation"])
        self.assertEqual((project["done"], project["total"], project["percent"]), (0, 3, 0))
        self.assertEqual([row["assignment"].title for row in r.context["rows"]], ["Einzelblatt"])
        self.assertContains(r, "0 von 3 erledigt")
        self.assertContains(r, "Weitere Arbeitsblätter")

    def test_progress_counts_finished_lessons_and_submissions(self):
        LessonResult.objects.create(lesson=self.cp.lessons.get(), student=self.student, completed=True)
        Submission.objects.create(assignment=self.cp.assignments.get(title="Präsentation"), student=self.student)
        project = self._home().context["projects"][0]
        self.assertEqual((project["done"], project["total"], project["percent"]), (2, 3, 67))
        self.assertFalse(project["complete"])
        Submission.objects.create(assignment=self.cp.assignments.get(title="Arbeitsblatt 1"), student=self.student)
        r = self._home()
        self.assertTrue(r.context["projects"][0]["complete"])
        self.assertContains(r, "✓ fertig")

    def test_pure_material_does_not_count_as_a_to_do(self):
        self.cp.assignments.filter(title="Arbeitsblatt 1").update(collect_submissions=False)
        project = self._home().context["projects"][0]
        self.assertEqual(project["total"], 2)  # lesson + task

    def test_pupils_of_another_class_do_not_see_the_project(self):
        other_student = Student.objects.create(school_class=self.sc2)
        self.client.get(reverse("schools:student_space", args=[other_student.access_code]))
        r = self._home()
        self.assertEqual(r.context["projects"], [])

    def test_task_card_shows_the_upload_area(self):
        r = self._home()
        self.assertContains(r, "Erstelle eine Präsentation.")
        self.assertContains(r, 'class="dropzone dropzone-lg js-dropzone"', count=3)  # worksheet, task, Einzelblatt


class AssignmentFromMaterialTests(ProjectTestBase):
    def test_hand_out_a_worksheet_straight_from_my_material(self):
        mine = MaterialFile.objects.create(owner=self.teacher, file=pdf("aus-material.pdf", b"MATERIAL"))
        self.client.post(
            reverse("worksheets:assignment_create", args=[self.sc.pk]),
            {"title": "Aus Material", "description": "", "collect_submissions": "on",
             "due_date_0": "", "due_date_1": "08:00", "material_files": [mine.pk]},
        )
        a = Assignment.objects.get(title="Aus Material")
        copy = a.files.get()
        self.assertEqual((copy.original_name, copy.file.read()), ("aus-material.pdf", b"MATERIAL"))
        self.assertNotEqual(copy.file.path, mine.file.path)

    def test_foreign_material_is_refused(self):
        theirs = MaterialFile.objects.create(owner=make_teacher("x@example.com"), file=pdf("fremd.pdf"))
        self.client.post(
            reverse("worksheets:assignment_create", args=[self.sc.pk]),
            {"title": "Klau", "description": "", "due_date_0": "", "due_date_1": "08:00", "material_files": [theirs.pk]},
        )
        self.assertFalse(Assignment.objects.filter(title="Klau").exists())

    def test_picker_is_shown_with_my_files_only(self):
        MaterialFile.objects.create(owner=self.teacher, file=pdf("meins.pdf"))
        MaterialFile.objects.create(owner=make_teacher("y@example.com"), file=pdf("fremd.pdf"))
        r = self.client.get(reverse("worksheets:assignment_create", args=[self.sc.pk]))
        self.assertContains(r, "meins.pdf")
        self.assertNotContains(r, "fremd.pdf")
