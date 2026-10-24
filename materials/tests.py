import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import MaterialFile, MaterialFolder
from .services import build_tree, descendant_ids, folder_choices

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def make_teacher(email):
    return User.objects.create_user(email=email, password="pw-strong-123", first_name="T", last_name="L")


def upload(name="blatt.pdf", content=b"%PDF-1.4 inhalt"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MaterialTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.teacher = make_teacher("m@example.com")
        self.other = make_teacher("o@example.com")
        self.client.force_login(self.teacher)

    def _folder(self, name, parent=None, owner=None):
        return MaterialFolder.objects.create(owner=owner or self.teacher, parent=parent, name=name)

    def _file(self, folder=None, name="blatt.pdf", owner=None):
        return MaterialFile.objects.create(owner=owner or self.teacher, folder=folder, file=upload(name))

    # --- access ------------------------------------------------------------

    def test_login_required(self):
        self.client.logout()
        r = self.client.get(reverse("materials:home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/konto/anmelden/", r["Location"])

    def test_empty_library_renders(self):
        r = self.client.get(reverse("materials:home"))
        self.assertContains(r, "Mein Material")
        self.assertContains(r, "dropzone-lg")

    def test_other_teacher_cannot_touch_my_material(self):
        folder = self._folder("Privat")
        mf = self._file(folder)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(folder.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(mf.get_download_url()).status_code, 404)
        for name, obj in (("folder_delete", folder), ("folder_rename", folder), ("file_delete", mf), ("file_rename", mf)):
            r = self.client.post(reverse(f"materials:{name}", args=[obj.pk]), {"name": "x"})
            self.assertEqual(r.status_code, 404, name)
        self.assertTrue(MaterialFile.objects.filter(pk=mf.pk).exists())
        # ... and cannot upload into or create inside my folder either
        r = self.client.post(reverse("materials:folder_create"), {"parent": folder.pk, "name": "Intruder"})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(reverse("materials:upload"), {"folder": folder.pk, "files": upload()})
        self.assertEqual(r.status_code, 404)

    # --- folders -----------------------------------------------------------

    def test_create_nested_folders(self):
        self.client.post(reverse("materials:folder_create"), {"parent": "", "name": "Informatik 7"})
        top = MaterialFolder.objects.get(name="Informatik 7")
        self.assertIsNone(top.parent)
        self.client.post(reverse("materials:folder_create"), {"parent": top.pk, "name": "Stunde 4"})
        sub = MaterialFolder.objects.get(name="Stunde 4")
        self.assertEqual(sub.parent, top)
        r = self.client.get(sub.get_absolute_url())
        self.assertContains(r, "Informatik 7")  # breadcrumb
        self.assertContains(r, "Stunde 4")

    def test_folder_names_are_validated(self):
        self._folder("Mathe")
        for bad in ("mathe", "  MATHE ", "a/b", "a\\b", "   "):
            self.client.post(reverse("materials:folder_create"), {"parent": "", "name": bad})
        self.assertEqual(MaterialFolder.objects.count(), 1)
        # same name in a different parent is fine
        other = self._folder("Physik")
        self.client.post(reverse("materials:folder_create"), {"parent": other.pk, "name": "Mathe"})
        self.assertEqual(MaterialFolder.objects.filter(name="Mathe").count(), 2)

    def test_rename_folder(self):
        folder = self._folder("Alt")
        self._folder("Belegt")
        self.client.post(reverse("materials:folder_rename", args=[folder.pk]), {"name": "Neu"})
        folder.refresh_from_db()
        self.assertEqual(folder.name, "Neu")
        self.client.post(reverse("materials:folder_rename", args=[folder.pk]), {"name": "belegt"})
        folder.refresh_from_db()
        self.assertEqual(folder.name, "Neu")  # duplicate sibling name refused

    def test_cannot_move_folder_into_itself_or_a_descendant(self):
        a = self._folder("A")
        b = self._folder("B", parent=a)
        c = self._folder("C", parent=b)
        for target in (a, b, c):
            self.client.post(reverse("materials:folder_move", args=[a.pk]), {"target": target.pk})
        a.refresh_from_db()
        self.assertIsNone(a.parent)
        self.assertEqual(descendant_ids(a), {b.pk, c.pk})

    def test_move_folder_and_back_to_root(self):
        a, b = self._folder("A"), self._folder("B")
        self.client.post(reverse("materials:folder_move", args=[b.pk]), {"target": a.pk})
        b.refresh_from_db()
        self.assertEqual(b.parent, a)
        self.client.post(reverse("materials:folder_move", args=[b.pk]), {"target": "root"})
        b.refresh_from_db()
        self.assertIsNone(b.parent)

    def test_delete_folder_removes_everything_including_blobs(self):
        a = self._folder("A")
        b = self._folder("B", parent=a)
        f1, f2 = self._file(a, "eins.pdf"), self._file(b, "zwei.pdf")
        keep = self._file(None, "bleibt.pdf")
        paths = [f1.file.path, f2.file.path]
        self.assertTrue(all(os.path.exists(p) for p in paths))
        self.client.post(reverse("materials:folder_delete", args=[a.pk]))
        self.assertFalse(MaterialFolder.objects.filter(pk__in=[a.pk, b.pk]).exists())
        self.assertFalse(MaterialFile.objects.filter(pk__in=[f1.pk, f2.pk]).exists())
        self.assertFalse(any(os.path.exists(p) for p in paths), "blobs must not stay on disk")
        self.assertTrue(os.path.exists(keep.file.path))

    # --- files -------------------------------------------------------------

    def test_upload_several_files_into_a_folder(self):
        folder = self._folder("Ablage")
        r = self.client.post(
            reverse("materials:upload"),
            {"folder": folder.pk, "files": [upload("a.pdf", b"AAA"), upload("b.pdf", b"BBB")]},
            follow=True,
        )
        self.assertContains(r, "2 Datei(en) hochgeladen")
        self.assertEqual(sorted(folder.files.values_list("original_name", flat=True)), ["a.pdf", "b.pdf"])
        self.assertEqual(folder.files.get(original_name="a.pdf").size, 3)

    def test_upload_to_root_and_download(self):
        self.client.post(reverse("materials:upload"), {"folder": "", "files": upload("wurzel.pdf", b"INHALT")})
        mf = MaterialFile.objects.get(original_name="wurzel.pdf")
        self.assertIsNone(mf.folder)
        r = self.client.get(mf.get_download_url())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"INHALT")
        self.assertIn("attachment", r["Content-Disposition"])

    def test_upload_without_file_is_refused(self):
        r = self.client.post(reverse("materials:upload"), {"folder": ""}, follow=True)
        self.assertEqual(MaterialFile.objects.count(), 0)
        self.assertEqual(r.status_code, 200)

    def test_rename_move_delete_file(self):
        folder = self._folder("Ziel")
        mf = self._file()
        self.client.post(reverse("materials:file_rename", args=[mf.pk]), {"name": "Neuer Name.pdf"})
        self.client.post(reverse("materials:file_move", args=[mf.pk]), {"target": folder.pk})
        mf.refresh_from_db()
        self.assertEqual((mf.original_name, mf.folder), ("Neuer Name.pdf", folder))
        path = mf.file.path
        self.client.post(reverse("materials:file_delete", args=[mf.pk]))
        self.assertFalse(MaterialFile.objects.filter(pk=mf.pk).exists())
        self.assertFalse(os.path.exists(path))

    def test_cannot_move_file_into_foreign_folder(self):
        foreign = self._folder("Fremd", owner=self.other)
        mf = self._file()
        r = self.client.post(reverse("materials:file_move", args=[mf.pk]), {"target": foreign.pk})
        self.assertEqual(r.status_code, 404)
        mf.refresh_from_db()
        self.assertIsNone(mf.folder)

    # --- helpers -----------------------------------------------------------

    def test_tree_flags_folders_with_selected_files(self):
        a = self._folder("A")
        b = self._folder("B", parent=a)
        deep = self._file(b, "tief.pdf")
        self._file(None, "oben.pdf")
        tree = build_tree(self.teacher, {deep.pk})
        self.assertEqual([f.original_name for f in tree["files"]], ["oben.pdf"])
        node_a = tree["nodes"][0]
        self.assertTrue(node_a["has_selected"])
        self.assertTrue(node_a["children"][0]["has_selected"])
        self.assertFalse(build_tree(self.teacher)["nodes"][0]["has_selected"])

    def test_folder_choices_show_full_path(self):
        a = self._folder("Informatik")
        self._folder("Klasse 7", parent=a)
        self.assertEqual([label for _, label in folder_choices(self.teacher)], ["Informatik", "Informatik / Klasse 7"])
