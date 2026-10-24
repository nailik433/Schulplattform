"""Helpers for the material library: folder trees, paths, safe deletion."""

from collections import defaultdict

from .models import MaterialFile, MaterialFolder


def _folder_maps(owner):
    folders = list(MaterialFolder.objects.filter(owner=owner))
    by_id = {f.pk: f for f in folders}
    children = defaultdict(list)
    for f in folders:
        children[f.parent_id].append(f)
    for kids in children.values():
        kids.sort(key=lambda f: f.name.lower())
    return by_id, children


def breadcrumbs(folder):
    """Ancestors of ``folder`` from the root down to and including it."""
    trail = []
    node = folder
    while node is not None:
        trail.append(node)
        node = node.parent
    return list(reversed(trail))


def descendant_ids(folder):
    """Primary keys of all folders below ``folder`` (not including it)."""
    _, children = _folder_maps(folder.owner)
    found, stack = set(), [folder.pk]
    while stack:
        for child in children.get(stack.pop(), []):
            if child.pk not in found:
                found.add(child.pk)
                stack.append(child.pk)
    return found


def folder_choices(owner):
    """``[(pk, "Ordner / Unterordner"), ...]`` for every folder, depth first."""
    by_id, children = _folder_maps(owner)

    def label(folder):
        parts, node = [], folder
        while node is not None:
            parts.append(node.name)
            node = by_id.get(node.parent_id)
        return " / ".join(reversed(parts))

    out = []

    def walk(parent_id):
        for f in children.get(parent_id, []):
            out.append((f.pk, label(f)))
            walk(f.pk)

    walk(None)
    return out


def build_tree(owner, selected=()):
    """Nested structure for the file picker:
    ``{"nodes": [{"folder", "children", "files", "has_selected"}], "files": [root files]}``.

    Folders that contain (or lead to) a selected file are flagged so the
    picker can show them expanded."""
    selected = set(selected)
    _, children = _folder_maps(owner)
    files_by_folder = defaultdict(list)
    for mf in MaterialFile.objects.filter(owner=owner):
        files_by_folder[mf.folder_id].append(mf)

    def nodes(parent_id):
        out = []
        for f in children.get(parent_id, []):
            kids = nodes(f.pk)
            own = files_by_folder.get(f.pk, [])
            out.append(
                {
                    "folder": f,
                    "children": kids,
                    "files": own,
                    "has_selected": any(mf.pk in selected for mf in own)
                    or any(k["has_selected"] for k in kids),
                }
            )
        return out

    return {"nodes": nodes(None), "files": files_by_folder.get(None, [])}


def attach_material(assignment, material_files):
    """Copy library files into an assignment. They are *copied* so deleting
    or renaming the library file later never breaks what pupils already got."""
    from django.core.files.base import ContentFile

    from worksheets.models import AssignmentFile

    created = []
    for mf in material_files:
        with mf.file.open("rb") as handle:
            data = handle.read()
        created.append(
            AssignmentFile.objects.create(
                assignment=assignment, file=ContentFile(data, name=mf.original_name)
            )
        )
    return created


def delete_file(material_file):
    material_file.file.delete(save=False)
    material_file.delete()


def delete_folder_tree(folder):
    """Delete a folder with everything below it, including the stored blobs
    (the database cascade alone would leave the files on disk)."""
    ids = {folder.pk} | descendant_ids(folder)
    for mf in MaterialFile.objects.filter(folder_id__in=ids):
        mf.file.delete(save=False)
    folder.delete()


def format_size(num_bytes):
    if num_bytes < 1024 * 1024:
        return f"{max(1, round(num_bytes / 1024))} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB".replace(".", ",")
