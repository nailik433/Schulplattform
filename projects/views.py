from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from materials.services import build_tree
from schools.models import SchoolClass

from . import services
from .forms import ApplyProjectForm, ApplyToClassesForm, ProjectForm, ProjectItemForm
from .models import ClassProject, Project, ProjectItem


# --------------------------------------------------------------------------
# Access helpers
# --------------------------------------------------------------------------

def _project_or_404(user, pk):
    return get_object_or_404(Project, pk=pk, owner=user)


def _item_or_404(user, pk):
    return get_object_or_404(ProjectItem.objects.select_related("project"), pk=pk, project__owner=user)


def _class_or_404(user, pk):
    return get_object_or_404(SchoolClass.objects.filter(memberships__teacher=user).distinct(), pk=pk)


def _class_project_or_404(user, pk):
    return get_object_or_404(
        ClassProject.objects.select_related("school_class", "project").filter(
            school_class__memberships__teacher=user
        ).distinct(),
        pk=pk,
    )


def _kind_or_404(raw):
    if raw not in ProjectItem.Kind.values:
        raise Http404
    return raw


# --------------------------------------------------------------------------
# Project templates
# --------------------------------------------------------------------------

@login_required
def project_list(request):
    projects = Project.objects.filter(owner=request.user).annotate(
        n_items=Count("items", distinct=True), n_used=Count("class_projects", distinct=True)
    )
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        messages.success(request, "Projekt angelegt. Jetzt Bausteine hinzufügen.")
        return redirect(project.get_absolute_url())
    return render(request, "projects/project_form.html", {"form": form})


@login_required
def project_edit(request, pk):
    project = _project_or_404(request.user, pk)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projekt gespeichert.")
        return redirect(project.get_absolute_url())
    return render(request, "projects/project_form.html", {"form": form, "project": project})


@login_required
def project_detail(request, pk):
    project = _project_or_404(request.user, pk)
    items = project.items.prefetch_related("material_files")
    used = project.class_projects.select_related("school_class").filter(
        school_class__memberships__teacher=request.user
    ).distinct()
    return render(
        request,
        "projects/project_detail.html",
        {"project": project, "items": items, "used": used, "kinds": ProjectItem.Kind},
    )


@login_required
@require_POST
def project_delete(request, pk):
    project = _project_or_404(request.user, pk)
    title = project.title
    project.delete()
    messages.success(
        request,
        f"Projekt „{title}“ gelöscht. Was schon in Klassen eingesetzt wurde, bleibt dort bestehen.",
    )
    return redirect("projects:list")


# --------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------

def _item_form_response(request, form, project, kind, item=None):
    selected = set()
    if form.is_bound:
        selected = {int(v) for v in request.POST.getlist("material_files") if v.isdigit()}
    elif item is not None:
        selected = set(item.material_files.values_list("pk", flat=True))
    return render(
        request,
        "projects/item_form.html",
        {
            "form": form,
            "project": project,
            "item": item,
            "kind": kind,
            "kind_label": ProjectItem.Kind(kind).label,
            "tree": build_tree(request.user, selected),
            "selected": selected,
        },
    )


@login_required
def item_create(request, pk, kind):
    project = _project_or_404(request.user, pk)
    kind = _kind_or_404(kind)
    form = ProjectItemForm(request.POST or None, kind=kind, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.instance.project = project
        form.instance.position = (
            project.items.order_by("-position").values_list("position", flat=True).first() or 0
        ) + 1
        item = form.save()
        project.save(update_fields=["updated_at"])
        messages.success(request, f"Baustein „{item.title}“ hinzugefügt.")
        return redirect(project.get_absolute_url())
    return _item_form_response(request, form, project, kind)


@login_required
def item_edit(request, pk):
    item = _item_or_404(request.user, pk)
    form = ProjectItemForm(request.POST or None, instance=item, kind=item.kind, owner=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        item.project.save(update_fields=["updated_at"])
        messages.success(request, "Baustein gespeichert.")
        return redirect(item.project.get_absolute_url())
    return _item_form_response(request, form, item.project, item.kind, item=item)


@login_required
@require_POST
def item_delete(request, pk):
    item = _item_or_404(request.user, pk)
    project, title = item.project, item.title
    item.delete()
    services.renumber(project)
    messages.success(request, f"Baustein „{title}“ entfernt.")
    return redirect(project.get_absolute_url())


@login_required
@require_POST
def item_move(request, pk, direction):
    if direction not in ("hoch", "runter"):
        raise Http404
    item = _item_or_404(request.user, pk)
    project = item.project
    services.renumber(project)
    items = list(project.items.all())
    index = next(i for i, it in enumerate(items) if it.pk == item.pk)
    neighbour = index - 1 if direction == "hoch" else index + 1
    if 0 <= neighbour < len(items):
        a, b = items[index], items[neighbour]
        ProjectItem.objects.filter(pk=a.pk).update(position=b.position)
        ProjectItem.objects.filter(pk=b.pk).update(position=a.position)
    return redirect(project.get_absolute_url())


# --------------------------------------------------------------------------
# Applying a template to classes
# --------------------------------------------------------------------------

@login_required
def project_apply(request, pk):
    project = _project_or_404(request.user, pk)
    initial = {}
    preselect = request.GET.get("klasse")
    if preselect and preselect.isdigit():
        initial["classes"] = [int(preselect)]
    form = ApplyToClassesForm(request.POST or None, owner=request.user, initial=initial)
    if not project.items.exists():
        messages.error(request, "Das Projekt hat noch keine Bausteine.")
        return redirect(project.get_absolute_url())
    if request.method == "POST" and form.is_valid():
        created = [
            services.instantiate_project(project, school_class, request.user, form.cleaned_data["due_date"])
            for school_class in form.cleaned_data["classes"]
        ]
        names = ", ".join(cp.school_class.name for cp in created)
        messages.success(request, f"Projekt „{project.title}“ ist jetzt in {names} eingesetzt.")
        if len(created) == 1:
            return redirect(created[0].get_absolute_url())
        return redirect(project.get_absolute_url())
    return render(request, "projects/apply.html", {"project": project, "form": form})


@login_required
def class_apply(request, class_pk):
    school_class = _class_or_404(request.user, class_pk)
    form = ApplyProjectForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.cleaned_data["project"]
        if not project.items.exists():
            messages.error(request, "Das Projekt hat noch keine Bausteine.")
        else:
            cp = services.instantiate_project(project, school_class, request.user, form.cleaned_data["due_date"])
            messages.success(request, f"Projekt „{project.title}“ in {school_class.name} eingesetzt.")
            return redirect(cp.get_absolute_url())
    has_projects = Project.objects.filter(owner=request.user).exists()
    return render(
        request,
        "projects/class_apply.html",
        {"school_class": school_class, "form": form, "has_projects": has_projects},
    )


# --------------------------------------------------------------------------
# A project inside a class
# --------------------------------------------------------------------------

@login_required
def class_project_detail(request, pk):
    cp = _class_project_or_404(request.user, pk)
    active = cp.school_class.students.filter(is_active=True).count()
    lessons = cp.lessons.annotate(n_done=Count("results", filter=Q(results__completed=True), distinct=True))
    assignments = cp.assignments.annotate(n_sub=Count("submissions", distinct=True))
    items = [{"kind": "lesson", "obj": o, "done": o.n_done} for o in lessons]
    items += [{"kind": "assignment", "obj": o, "done": o.n_sub} for o in assignments]
    items.sort(key=lambda row: (row["obj"].project_order, row["obj"].pk))
    return render(
        request,
        "projects/class_project_detail.html",
        {"cp": cp, "items": items, "active": active},
    )


@login_required
@require_POST
def class_project_detach(request, pk):
    cp = _class_project_or_404(request.user, pk)
    school_class, title = cp.school_class, cp.title
    cp.delete()  # items stay (SET_NULL) and show up as individual lessons/worksheets
    messages.success(request, f"Projekt „{title}“ aufgelöst. Die Bausteine bleiben einzeln in der Klasse.")
    return redirect(school_class.get_absolute_url())


@login_required
@require_POST
def class_project_delete(request, pk):
    cp = _class_project_or_404(request.user, pk)
    school_class, title = cp.school_class, cp.title
    services.delete_class_project_with_items(cp)
    messages.success(request, f"Projekt „{title}“ samt allen Bausteinen und Abgaben gelöscht.")
    return redirect(school_class.get_absolute_url())
