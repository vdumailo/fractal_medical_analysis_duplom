from django import forms
from django.contrib.auth.forms import AuthenticationForm


def apply_bootstrap_classes(form: forms.Form) -> None:
    for name, field in form.fields.items():
        widget = field.widget
        classes = widget.attrs.get('class', '').split()

        if isinstance(widget, forms.CheckboxInput):
            classes.append('form-check-input')
        elif isinstance(widget, forms.Select):
            classes.append('form-select')
        else:
            classes.append('form-control')

        widget.attrs['class'] = ' '.join(sorted(set(filter(None, classes))))

        if not isinstance(widget, (forms.CheckboxInput, forms.Select, forms.FileInput)):
            widget.attrs.setdefault('placeholder', field.label or '')

        if field.required and not isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault('required', 'required')


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap_classes(self)


class StyledAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(label='Логін')
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'
        self.fields['username'].widget.attrs['placeholder'] = 'Введіть логін'
        self.fields['password'].widget.attrs['placeholder'] = 'Введіть пароль'
