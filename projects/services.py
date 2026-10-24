"""Applying project templates to classes, and removing them again."""

from django.db import transaction

from materials.services import attach_material

from .models import ClassProject, ProjectItem


@transaction.atomic
def instantiate_project(project, school_class, teacher, due=None):
    """Copy every block of ``project`` into ``school_class``.

    Learning environments become :class:`lessons.models.Lesson`, worksheets
    and tasks become :class:`worksheets.models.Assignment`, all tied to a new
    :class:`ClassProject` so pupils see them bundled. ``due`` (optional) is
    used as deadline for every block that collects submissions."""
    from lessons.models import Lesson
    from worksheets.models import Assignment

    class_project = ClassProject.objects.create(
        school_class=school_class,
        project=project,
        title=project.title,
        description=project.description,
        created_by=teacher,
    )
    for index, item in enumerate(project.items.prefetch_related("material_files"), start=1):
        if item.kind == ProjectItem.Kind.LESSON:
            Lesson.objects.create(
                school_class=school_class,
                title=item.title,
                html=item.html,
                created_by=teacher,
                class_project=class_project,
                project_order=index,
            )
            continue
        collect = True if item.kind == ProjectItem.Kind.TASK else item.collect_submissions
        assignment = Assignment.objects.create(
            school_class=school_class,
            title=item.title,
            description=item.description,
            collect_submissions=collect,
            due_date=due if collect else None,
            created_by=teacher,
            class_project=class_project,
            project_order=index,
        )
        if item.kind == ProjectItem.Kind.WORKSHEET:
            attach_material(assignment, item.material_files.all())
    return class_project


def delete_class_project_with_items(class_project):
    """Delete a project in a class together with its lessons, assignments,
    submissions and all stored files (the database cascade would leave the
    blobs on disk)."""
    from worksheets.models import AssignmentFile, SubmissionFile

    for af in AssignmentFile.objects.filter(assignment__class_project=class_project):
        af.file.delete(save=False)
    for sf in SubmissionFile.objects.filter(submission__assignment__class_project=class_project):
        sf.file.delete(save=False)
    class_project.lessons.all().delete()
    class_project.assignments.all().delete()
    class_project.delete()


def renumber(project):
    """Make ``position`` a gap-free 1..n sequence."""
    for index, item in enumerate(project.items.all(), start=1):
        if item.position != index:
            ProjectItem.objects.filter(pk=item.pk).update(position=index)
