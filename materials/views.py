from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import FileNameForm, FolderNameForm, UploadForm
from .models import MaterialFile, MaterialFolder


# --------------------------------------------------------------------------
# Helpers: everything here belongs to exactly one teacher (the owner)
# --------------------------------------------------------------------------

def _folder_or_404(user, pk):
    return get_object_or_404(MaterialFolder.objects.select_related("parent"), pk=pk, owner=user)


def _file_or_404(user, pk):
    return get_object_or_404(MaterialFile.objects.select_related("folder"), pk=pk, owner=user)


def _optional_folder(user, raw):
    """The folder named by a POST value, ``None`` for the root. 404 if the
    value names a folder that is not the user's."""
    if raw in (None, "", "root"):
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        raise Http404
    return _folder_or_404(user, pk)


def _back(folder):
    return redirect(folder.get_absolute_url() if folder else "materials:home")


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return "Das hat nicht geklappt."


# --------------------------------------------------------------------------
# Browsing
# --------------------------------------------------------------------------

@login_required
def browse(request, folder_pk=None):
    user = request.user
    folder = _folder_or_404(user, folder_pk) if folder_pk else None
    choices = services.folder_choices(user)

    folders = (
        MaterialFolder.objects.filter(owner=user, parent=folder)
        .annotate(n_folders=Count("children", distinct=True), n_files=Count("files", distinct=True))
    )
    files = MaterialFile.objects.filter(owner=user, folder=folder)

    folder_rows = []
    for f in folders:
        blocked = services.descendant_ids(f) | {f.pk}
        folder_rows.append(
            {
                "folder": f,
                "options": [(pk, label) for pk, label in choices if pk not in blocked and pk != f.parent_id],
                "to_root": f.parent_id is not None,
            }
        )
    file_rows = [
        {
            "file": mf,
            "size": services.format_size(mf.size),
            "options": [(pk, label) for pk, label in choices if pk != mf.folder_id],
            "to_root": mf.folder_id is not None,
        }
        for mf in files
    ]
    total = MaterialFile.objects.filter(owner=user).aggregate(s=Sum("size"))["s"] or 0
    return render(
        request,
        "materials/browser.html",
        {
            "folder": folder,
            "crumbs": services.breadcrumbs(folder) if folder else [],
            "folder_rows": folder_rows,
            "file_rows": file_rows,
            "total_size": services.format_size(total),
        },
    )


# --------------------------------------------------------------------------
# Folders
# --------------------------------------------------------------------------

@login_required
@require_POST
def folder_create(request):
    parent = _optional_folder(request.user, request.POST.get("parent"))
    form = FolderNameForm(request.POST, owner=request.user, parent=parent)
    if form.is_valid():
        MaterialFolder.objects.create(owner=request.user, parent=parent, name=form.cleaned_data["name"])
        messages.success(request, f"Ordner „{form.cleaned_data['name']}“ angelegt.")
    else:
        messages.error(request, _first_error(form))
    return _back(parent)


@login_required
@require_POST
def folder_rename(request, pk):
    folder = _folder_or_404(request.user, pk)
    form = FolderNameForm(request.POST, owner=request.user, parent=folder.parent, exclude_pk=folder.pk)
    if form.is_valid():
        folder.name = form.cleaned_data["name"]
        folder.save(update_fields=["name"])
        messages.success(request, "Ordner umbenannt.")
    else:
        messages.error(request, _first_error(form))
    return _back(folder.parent)


@login_required
@require_POST
def folder_move(request, pk):
    folder = _folder_or_404(request.user, pk)
    target = _optional_folder(request.user, request.POST.get("target"))
    if target is not None and (target.pk == folder.pk or target.pk in services.descendant_ids(folder)):
        messages.error(request, "Ein Ordner kann nicht in sich selbst oder einen seiner Unterordner verschoben werden.")
        return _back(folder.parent)
    clash = MaterialFolder.objects.filter(owner=request.user, parent=target, name__iexact=folder.name).exclude(pk=folder.pk)
    if clash.exists():
        messages.error(request, f"Im Zielordner gibt es schon einen Ordner „{folder.name}“.")
        return _back(folder.parent)
    old_parent = folder.parent
    folder.parent = target
    folder.save(update_fields=["parent"])
    messages.success(request, f"„{folder.name}“ verschoben.")
    return _back(old_parent)


@login_required
@require_POST
def folder_delete(request, pk):
    folder = _folder_or_404(request.user, pk)
    parent, name = folder.parent, folder.name
    services.delete_folder_tree(folder)
    messages.success(request, f"Ordner „{name}“ mit allem Inhalt gelöscht.")
    return _back(parent)


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

@login_required
@require_POST
def upload(request):
    folder = _optional_folder(request.user, request.POST.get("folder"))
    form = UploadForm(request.POST, request.FILES)
    if form.is_valid():
        count = 0
        for upload_file in form.cleaned_data["files"]:
            if upload_file:
                MaterialFile.objects.create(owner=request.user, folder=folder, file=upload_file)
                count += 1
        messages.success(request, f"{count} Datei(en) hochgeladen.")
    else:
        messages.error(request, _first_error(form) if form.errors else "Upload fehlgeschlagen.")
    return _back(folder)


@login_required
@require_POST
def file_rename(request, pk):
    mf = _file_or_404(request.user, pk)
    form = FileNameForm(request.POST)
    if form.is_valid():
        mf.original_name = form.cleaned_data["name"]
        mf.save(update_fields=["original_name"])
        messages.success(request, "Datei umbenannt.")
    else:
        messages.error(request, _first_error(form))
    return _back(mf.folder)


@login_required
@require_POST
def file_move(request, pk):
    mf = _file_or_404(request.user, pk)
    target = _optional_folder(request.user, request.POST.get("target"))
    old = mf.folder
    mf.folder = target
    mf.save(update_fields=["folder"])
    messages.success(request, f"„{mf.original_name}“ verschoben.")
    return _back(old)


@login_required
@require_POST
def file_delete(request, pk):
    mf = _file_or_404(request.user, pk)
    folder, name = mf.folder, mf.original_name
    services.delete_file(mf)
    messages.success(request, f"„{name}“ gelöscht.")
    return _back(folder)


@login_required
def file_download(request, pk):
    mf = _file_or_404(request.user, pk)
    try:
        handle = mf.file.open("rb")
    except FileNotFoundError:
        raise Http404
    return FileResponse(handle, as_attachment=True, filename=mf.original_name)
