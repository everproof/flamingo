from datetime import datetime

from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import generic
from django.views.generic import TemplateView

from accounts.models import User
from courses.models import Course, Curriculum, Provider, Qualification
from flamingo.forms import (AddMemberForm, AddRequirementForm, AddRoleForm,
                            AddUserForm, EditRequirementForm,
                            SelectRoleRequirementsForm)
from organisations.models import Member, Organisation, Role, RoleRequirements


class OrgContextMixin(object):
    """
    Pass organisation context to any view.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = Organisation.objects.get(pk=self.kwargs['pk'])
        context['organisation'] = org
        return context


class OrgQuerysetMixin(object):
    """
    Filter the queryset to just contain objects related to specific org.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        org_id = self.kwargs['pk']
        queryset = queryset.filter(organisation=org_id)
        return queryset


class DetailsNavbarMixin(object):
    """
    Pass context into navbar that we're in details tab
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nbar'] = 'details'
        return context


class MembersNavbarMixin(object):
    """
    Pass context into navbar that we're in members tab
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nbar'] = 'members'
        return context


class RolesNavbarMixin(object):
    """
    Pass context into navbar that we're in roles tab
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nbar'] = 'roles'
        return context


class RequirementsNavbarMixin(object):
    """
    Pass context into navbar that we're in requirements tab
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nbar'] = 'requirements'
        return context


class AjaxableResponseMixin(object):
    """
    Mixin to add AJAX support to a form.
    Must be used with an object-based FormView (e.g. CreateView)
    """
    def form_invalid(self, form):
        response = super().form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse(form.errors, status=400)
        return response


class OrgList(generic.ListView):
    """
    List organisations and filter by a search term.
    """
    model = Organisation
    context_object_name = 'organisations'
    template_name = 'flamingo/organisations/org_list.html'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('org')
        if query is not None:
            queryset = Organisation.objects.filter(name__icontains=query)
        return queryset.order_by('id')


class OrgDetails(DetailsNavbarMixin, generic.DetailView):
    """
    Display the details of an organisation.
    """
    model = Organisation
    template_name = 'flamingo/organisations/org_details.html'


class EditDetails(DetailsNavbarMixin, generic.UpdateView):
    """
    Edit the details of an organisation.
    """
    model = Organisation
    fields = ['name', 'address', 'industry']
    template_name = 'flamingo/organisations/org_details_edit.html'

    def get_success_url(self, *args, **kwargs):
        org_id = self.request.POST.get('org')
        return reverse('flamingo:org-details', args=[org_id])


class OrgMembers(MembersNavbarMixin, OrgContextMixin, OrgQuerysetMixin, generic.ListView):
    """
    List the members in an organisation.
    """
    model = Member
    context_object_name = 'members'
    template_name = 'flamingo/organisations/org_members.html'


class OrgUserList(MembersNavbarMixin, OrgContextMixin, generic.ListView):
    """
    List users searched when attempting to link a user as a member to an organisation.
    """
    model = User
    context_object_name = 'users'
    template_name = 'flamingo/organisations/org_users_list.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search_term = self.request.GET.get('user_search')
        queryset = queryset.filter((Q(first_name__icontains=search_term)
                                    | Q(last_name__icontains=search_term)
                                    | Q(email__icontains=search_term)))
        org_id = self.kwargs['pk']
        members = Member.objects.filter(user__in=queryset).filter(organisation__in=org_id)
        for member in members:
            queryset = queryset.exclude(id=member.user.id)
        return queryset.order_by('id')


def add_member(request, pk):
    """
    Creates a user and a member, linking them to an organisation.
    """
    org = Organisation.objects.get(pk=pk)
    if request.method == 'POST':
        user_form = AddUserForm(data=request.POST, prefix='user')
        member_form = AddMemberForm(data=request.POST, organisation=org, prefix='member')
        if user_form.is_valid() and member_form.is_valid():
            user = user_form.save()
            member = member_form.save(commit=False)
            member.user = user
            member.organisation = org
            member.save()
            # Since save is called initially with commit=False, many to many save must be used to save the roles field
            member_form.save_m2m()
            return HttpResponseRedirect(reverse('flamingo:org-members', args=[pk]))
        else:
            # TODO: Display in template
            print("form not valid")
    else:
        user_form = AddUserForm(prefix='user')
        member_form = AddMemberForm(prefix='member', organisation=org)

    context_dict = {
        'user_form': user_form,
        'member_form': member_form,
        'organisation': org,
        'nbar': "members"
    }
    return render(request, 'flamingo/organisations/org_members_add.html', context_dict)


def edit_member(request, pk, member_pk):
    """
    Edit a member's details (and the relevant user) who belongs to an organisation.
    """
    member = Member.objects.get(pk=member_pk)
    org = Organisation.objects.get(pk=pk)
    if request.method == 'POST':
        user_form = AddUserForm(data=request.POST, prefix='user', instance=member.user)
        member_form = AddMemberForm(data=request.POST, organisation=org, prefix='member', instance=member)
        if user_form.is_valid() and member_form.is_valid():
            user = user_form.save()
            member = member_form.save(commit=False)
            member.user = user
            member.organisation = org
            member.save()
            # Since save is called initially with commit=False, many to many save must be used to save the roles field
            member_form.save_m2m()
            return HttpResponseRedirect(reverse('flamingo:org-member', args=[pk, member.id]))
        else:
            # TODO: Produce an error msg
            print("Form not valid")
    else:
        user_form = AddUserForm(instance=member.user, prefix='user')
        member_form = AddMemberForm(instance=member, prefix='member', organisation=org)

    context_dict = {
        'user_form': user_form,
        'member_form': member_form,
        'organisation': org,
        'member': member,
        'nbar': "members"
    }
    return render(request, 'flamingo/organisations/org_members_edit.html', context_dict)


class OrgUserSearch(MembersNavbarMixin, OrgContextMixin, TemplateView):
    """
    Search for users to later link as members within an organisation.
    """
    template_name = 'flamingo/organisations/org_users_search.html'


class MemberDetails(MembersNavbarMixin, OrgContextMixin, generic.DetailView):
    """
    Display the details of a member.
    """
    model = Member
    template_name = 'flamingo/organisations/org_member.html'
    context_object_name = 'member'
    pk_url_kwarg = 'member_pk'


def link_user(request, org_id, user_id):
    """
    Link a user to an organisation by creating a member object.
    """
    org = Organisation.objects.get(pk=org_id)
    user = User.objects.get(pk=user_id)
    if request.method == 'POST':
        form = AddMemberForm(data=request.POST, organisation=org)
        if form.is_valid():
            member = form.save(commit=False)
            member.user = user
            member.organisation = org
            member.save()
            # Since save is called initially with commit=False, many to many save must be used to save the roles field
            form.save_m2m()
            return HttpResponseRedirect(reverse('flamingo:org-members', args=[org_id]))
        else:
            # TODO: Produce an error msg
            print("form not valid")
    else:
        form = AddMemberForm(organisation=org)
    context_dict = {
        'form': form,
        'organisation': org,
        'user': user,
        'nbar': "members",
    }
    return render(request, 'flamingo/organisations/org_link_details.html', context_dict)


class UnlinkMember(MembersNavbarMixin, generic.DeleteView):
    """
    Unlink a member from an organisation by deleting the member object.
    """
    model = Member
    slug_url_kwarg = 'org_id'
    slug_field = 'organisation'
    pk_url_kwarg = 'member_id'
    query_pk_and_slug = True

    def get_success_url(self):
        org_id = self.kwargs['org_id']
        url = reverse('flamingo:org-members', args=[org_id])
        return url


class OrgRequirements(RequirementsNavbarMixin, OrgContextMixin, OrgQuerysetMixin, generic.ListView):
    """
    List requirements for an organisation.
    """
    model = RoleRequirements
    context_object_name = 'requirements'
    template_name = 'flamingo/organisations/org_requirements.html'
    ordering = ['name']


class ViewRequirement(OrgContextMixin, RequirementsNavbarMixin, generic.DetailView):
    """
    View a requirement within an organisation.
    """
    model = RoleRequirements
    template_name = 'flamingo/organisations/org_requirement.html'
    context_object_name = 'requirement'
    pk_url_kwarg = 'requirement_pk'


class DeleteRequirement(OrgContextMixin, RequirementsNavbarMixin, generic.DeleteView):
    """
    Delete a requirement from an organisation.
    """
    model = RoleRequirements
    pk_url_kwarg = 'requirement_pk'

    def get_success_url(self):
        org_id = self.kwargs['pk']
        url = reverse('flamingo:org-requirements', args=[org_id])
        return url


def add_requirement(request, pk):
    """
    Add a requirement.
    """
    org = Organisation.objects.get(pk=pk)
    if request.method == 'POST':
        form = AddRequirementForm(org=org, data=request.POST)
        if form.is_valid():
            req = RoleRequirements()
            primary = Course.objects.get(pk=form.cleaned_data['primary'])
            # Set requirement name to title of primary document
            req.name = primary.title
            req.organisation = org
            req.save()
            # Add roles to the requirement object
            for role in form.cleaned_data['roles']:
                req.roles.add(role)
            # Add primary document to associated courses
            req.courses.add(primary)
            # Add alternatives to associated courses
            for alternative in form.cleaned_data['alternatives']:
                req.courses.add(alternative)
            req.save()
            return HttpResponseRedirect(reverse('flamingo:org-requirements', args=[pk]))
        else:
            # TODO: Produce an error msg
            return HttpResponseRedirect(reverse('flamingo:org-requirements', args=[pk]))
    else:
        form = AddRequirementForm(org=org)
    context = {
        'form': form,
        'organisation': org,
        'nbar': 'requirements'
    }
    return render(request, 'flamingo/organisations/org_requirement_add.html', context)


def edit_requirement(request, pk, requirement_pk):
    """
    Edit a requirement.
    """
    org = Organisation.objects.get(pk=pk)
    req = RoleRequirements.objects.get(pk=requirement_pk)
    primary = Course.objects.get(title=req.name)
    # Get initial requirement data to render the form
    req_roles_ids = list(req.roles.all().values_list('id', flat=True))
    req_courses_ids = list(req.courses.exclude(title=req.name).values_list('id', flat=True))
    initial_reqs_data = {
        'roles': req_roles_ids,
        'alternatives': req_courses_ids,
        'primary': primary.id
    }
    if request.method == 'POST':
        form = EditRequirementForm(org=org, data=request.POST, current_req=req)
        if form.is_valid():
            primary = Course.objects.get(pk=form.cleaned_data['primary'])
            # Set requirement name to title of primary document
            req.name = primary.title
            req.organisation = org
            req.save()
            # Remove all roles from requirement
            for role in req.roles.all():
                req.roles.remove(role)
            # Remove all courses from requirement
            for course in req.courses.all():
                req.courses.remove(course)
            # Add roles to the requirement object
            for role in form.cleaned_data['roles']:
                req.roles.add(role)
            # Add primary document to associated courses
            req.courses.add(primary)
            # Add alternatives to associated courses
            for alternative in form.cleaned_data['alternatives']:
                req.courses.add(alternative)
            req.save()
            return HttpResponseRedirect(reverse('flamingo:org-requirements', args=[pk]))
        else:
            # TODO: Produce an error msg
            return HttpResponseRedirect(reverse('flamingo:org-requirements', args=[pk]))
    else:
        form = EditRequirementForm(current_req=req, initial=initial_reqs_data, org=org)
    context = {
        'form': form,
        'organisation': org,
        'requirement': req,
        'nbar': 'requirements'
    }
    return render(request, 'flamingo/organisations/org_requirement_edit.html', context)


class ListRoles(RolesNavbarMixin, OrgContextMixin, generic.ListView):
    """
    List roles within an organisation
    """
    model = Role
    context_object_name = 'roles'
    template_name = 'flamingo/organisations/org_roles.html'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        org_id = self.kwargs['pk']
        queryset = queryset.filter(organisation=org_id)
        return queryset.order_by('id')


def add_role(request, pk):
    """
    Add a role.
    """
    org = Organisation.objects.get(pk=pk)
    if request.method == 'POST':
        role_form = AddRoleForm(data=request.POST)
        req_form = SelectRoleRequirementsForm(org=org, data=request.POST)
        if role_form.is_valid() and req_form.is_valid():
            role = Role()
            role.name = role_form.cleaned_data['name']
            role.organisation = org
            role.save()
            for req_id in req_form.cleaned_data['requirements']:
                req = RoleRequirements.objects.get(pk=req_id)
                req.roles.add(role)
            return HttpResponseRedirect(reverse('flamingo:org-roles', args=[pk]))
        else:
            HttpResponse("form invalid")
    else:
        role_form = AddRoleForm()
        req_form = SelectRoleRequirementsForm(org=org)
    context = {
        'organisation': org,
        'role_form': role_form,
        'req_form': req_form,
        'nbar': 'roles'
    }
    return render(request, 'flamingo/organisations/org_role_add.html', context)


def edit_role(request, pk, role_pk):
    """
    Edit a role.
    """
    org = Organisation.objects.get(pk=pk)
    role = Role.objects.get(pk=role_pk)
    reqs = role.role_requirements.all()
    # List of IDs for current requirements to pre-fill form
    reqs_ids = list(reqs.values_list('id', flat=True))
    initial_reqs_data = {'requirements': reqs_ids}
    if request.method == 'POST':
        role_form = AddRoleForm(data=request.POST)
        req_form = SelectRoleRequirementsForm(org=org, data=request.POST)
        if role_form.is_valid() and req_form.is_valid():
            role.name = role_form.cleaned_data['name']
            role.save()
            # Remove role from all requirements in org
            for req in reqs:
                req.roles.remove(role)
            # Add the role only to the requirements that are selcted
            for req_id in req_form.cleaned_data['requirements']:
                req = RoleRequirements.objects.get(pk=req_id)
                req.roles.add(role)
            return HttpResponseRedirect(reverse('flamingo:org-role', args=[pk, role_pk]))
        else:
            HttpResponse("form invalid")
    else:
        role_form = AddRoleForm(instance=role)
        req_form = SelectRoleRequirementsForm(initial=initial_reqs_data, org=org)
    context = {
        'organisation': org,
        'role_form': role_form,
        'req_form': req_form,
        'role': role,
        'nbar': 'roles'
    }
    return render(request, 'flamingo/organisations/org_role_edit.html', context)


class ViewRole(OrgContextMixin, RolesNavbarMixin, generic.DetailView):
    """
    View a role within an organisation
    """
    model = Role
    template_name = 'flamingo/organisations/org_role.html'
    context_object_name = 'role'
    pk_url_kwarg = 'role_pk'


class DeleteRole(OrgContextMixin, RolesNavbarMixin, generic.DeleteView):
    """
    Delete a role from an organisation.
    """
    model = Role
    slug_url_kwarg = 'org_id'
    slug_field = 'organisation'
    pk_url_kwarg = 'role_pk'
    query_pk_and_slug = True

    def get_success_url(self, *args, **kwargs):
        org_id = self.kwargs['pk']
        url = reverse('flamingo:org-roles', args=[org_id])
        return url


class UserList(generic.ListView):
    """
    List users and filter by a search term.
    """
    model = User
    context_object_name = 'users'
    template_name = 'flamingo/users/user_list.html'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('usr')
        if query is not None:
            queryset = User.objects.filter((Q(first_name__icontains=query)
                                            | Q(last_name__icontains=query)
                                            | Q(email__icontains=query)))
        return queryset.order_by('last_name')


class UserDetails(generic.DetailView):
    """
    Display the details of a specific user.
    """
    model = User
    template_name = 'flamingo/users/user_details.html'


class UserDocuments(generic.DetailView):
    """
    Display the documents (qualifications) held by a specific user.
    """
    model = User
    template_name = 'flamingo/users/user_documents.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Datetime used to calculate time until qualifications expire
        context['time'] = datetime.now()

        # Get the user, and all qualification the user holds
        usr = User.objects.get(pk=self.kwargs['pk'])

        # Key stores the org, and value stores an array of quals visible to that org
        tabs = {}

        # Creating a tab which shows all the user's qualifications
        tabs['All'] = [[qualification] for qualification in Qualification.objects.filter(user=usr).all()]

        # Look at each organisation which a user is in
        for membership in usr.memberships.all():
            org_tab = ([[qualification] for qualification
                        in Qualification.objects.filter(organisations=membership.organisation).all()])
            # Add it to that key (ie. that org tab)
            tabs[membership.organisation.name] = org_tab

        # Showing qualifications that are only visible to the user
        tabs['Only Me'] = ([[qualification] for qualification in
                            Qualification.objects.filter(organisations=None, user=usr).all()])

        # Add this dictionary to context
        context['tabs'] = tabs
        return context


class UserEditDetails(generic.UpdateView):
    """
    Edit the details of a user.
    """
    model = User
    fields = ['first_name', 'middle_name', 'last_name', 'email', 'phone', 'date_of_birth']
    template_name = 'flamingo/users/user_details_edit.html'

    def get_success_url(self, *args, **kwargs):
        user_id = self.request.POST.get('usr_pk')
        return reverse('flamingo:user-details', args=[user_id])


class UserEditDocuments(generic.UpdateView):
    """
    Edit a document belonging to a user
    """
    model = Qualification
    fields = ['document_number', 'organisations', 'attained_date', 'expiry_date', 'notes']
    template_name = 'flamingo/users/user_documents_edit.html'
    pk_url_kwarg = 'document_pk'

    def get_success_url(self, *args, **kwargs):
        user_id = self.request.POST.get('usr_pk')
        return reverse('flamingo:user-documents', args=[user_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usr = User.objects.get(pk=self.kwargs['pk'])
        context['user'] = usr
        return context


class CurriculumList(generic.ListView):
    """
    List curriculums and filter by a search term.
    """
    template_name = 'flamingo/curriculums/curriculums_list.html'
    paginate_by = 20
    model = Curriculum
    context_object_name = 'curriculums'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('search')
        if query is not None:
            queryset = Curriculum.objects.filter(Q(course__title__icontains=query)
                                                 | Q(provider__name__icontains=query))
        return queryset


class CurriculumDetails(generic.DetailView):
    """
    View details of a specific curriculum
    """
    model = Curriculum
    context_object_name = 'curriculum'
    template_name = 'flamingo/curriculums/curriculums_details.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        curriculum = Curriculum.objects.get(pk=self.kwargs['pk'])
        context['curriculum'] = curriculum

        # Get the users associated with a qualification
        users = ([qualification.user for qualification in
                 Qualification.objects.filter(course=curriculum.course, provider=curriculum.provider)])
        context['users'] = users
        return context


class CurriculumAdd(generic.CreateView):
    """
    Add a curriculum, using a pre-existing course and provider pair.
    """
    template_name = 'flamingo/curriculums/curriculums_add.html'
    model = Curriculum
    fields = ['course', 'provider']

    def get_success_url(self, *args, **kwargs):
        return reverse('flamingo:curriculums-list')


class CourseList(generic.ListView):
    """
    List course and filter by a search term.
    """
    template_name = 'flamingo/courses/courses_list.html'
    paginate_by = 20
    model = Course
    context_object_name = 'courses'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('search')
        if query is not None:
            queryset = Course.objects.filter(Q(title__icontains=query))
        return queryset


class ProviderList(generic.ListView):
    """
    List provider and filter by a search term.
    """
    template_name = 'flamingo/providers/providers_list.html'
    paginate_by = 20
    model = Provider
    context_object_name = 'providers'

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('search')
        if query is not None:
            queryset = Provider.objects.filter(Q(name__icontains=query))
        return queryset


class CourseEdit(generic.UpdateView):
    """
    Edit a course title
    """
    model = Course
    fields = ['title']
    template_name = 'flamingo/courses/courses_edit.html'
    pk_url_kwarg = 'course_pk'

    def get_success_url(self, *args, **kwargs):
        return reverse('flamingo:courses-list')


class CourseAdd(generic.CreateView):
    """
    Add a course
    """
    template_name = 'flamingo/courses/courses_add.html'
    model = Course
    fields = ['title']

    def get_success_url(self, *args, **kwargs):
        return reverse('flamingo:courses-list')


class ProviderEdit(generic.UpdateView):
    """
    Edit a provider name
    """
    template_name = 'flamingo/providers/providers_edit.html'
    model = Provider
    fields = ['name']
    pk_url_kwarg = 'provider_pk'

    def get_success_url(self, *args, **kwargs):
        return reverse('flamingo:providers-list')


class ProviderAdd(generic.CreateView):
    """
    Add a provider
    """
    template_name = 'flamingo/providers/providers_add.html'
    model = Provider
    fields = ['name']

    def get_success_url(self, *args, **kwargs):
        return reverse('flamingo:providers-list')
