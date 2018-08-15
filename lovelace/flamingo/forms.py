from django import forms
from django.forms import Form, ModelForm, SelectMultiple, TextInput

from accounts.models import User
from courses.models import Course
from organisations.models import Member, Role


class AddMemberForm(ModelForm):
    class Meta:
        model = Member
        fields = ['roles', 'level']

    # Only roles specific to the organisation shown
    def __init__(self, organisation, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['roles'].widget = SelectMultiple(attrs={
          'class': 'form-control'
          })
        self.fields['roles'].queryset = organisation.roles
        # if they are not an admin, they do not get assigned a level. they
        # are just a "person"
        self.fields['level'].choices = [("", "Person"), ] + list(self.fields["level"].choices)[1:]

    def clean(self):
        super().clean()


class AddUserForm(ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            for field in self.fields:
                self.fields[field].widget = TextInput(attrs={
                    'class': 'form-control'
                })


class AddRequirementForm(Form):
    alternatives = forms.MultipleChoiceField(required=False)
    roles = forms.MultipleChoiceField(required=False)
    primary = forms.ChoiceField()

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courses = Course.objects.all().order_by('title')
        self.fields['alternatives'].choices = courses.values_list('id', 'title')
        # Remove courses that are already "primary documents"
        current_reqs = org.role_requirements.all()
        for req in current_reqs:
            courses = courses.exclude(title=req.name)
        self.fields['primary'].choices = courses.values_list('id', 'title')
        self.fields['roles'].choices = org.roles.values_list('id', 'name')


class EditRequirementForm(Form):
    alternatives = forms.MultipleChoiceField(required=False)
    roles = forms.MultipleChoiceField()
    primary = forms.ChoiceField()

    def __init__(self, org, current_req, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courses = Course.objects.all().order_by('title')
        self.fields['alternatives'].choices = courses.values_list('id', 'title')
        current_reqs = org.role_requirements.all()
        for req in current_reqs:
            if req != current_req:
                courses = courses.exclude(title=req.name)
        self.fields['primary'].choices = courses.values_list('id', 'title')
        self.fields['roles'].choices = org.roles.values_list('id', 'name')


class AddRoleForm(ModelForm):
    class Meta:
        model = Role
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            for field in self.fields:
                self.fields[field].widget = TextInput(attrs={
                    'class': 'form-control'
                })


class SelectRoleRequirementsForm(Form):
    requirements = forms.MultipleChoiceField(required=False)

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reqs = org.role_requirements.all()
        self.fields['requirements'].widget = SelectMultiple(attrs={
            'id': 'selectRequirements',
            'class': 'form-control',
        })

        self.fields['requirements'].choices = reqs.values_list('id', 'name')
