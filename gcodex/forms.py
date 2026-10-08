from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class UploadCSVForm(forms.Form):
    csv_file = forms.FileField(
        label='Seleccioneu l\'arxiu CSV',
        widget=forms.FileInput(attrs={'accept': '.csv'}),
        help_text='Exporteu el fitxer .csv',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.add_input(Submit('submit', 'Pujar CSV'))

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            if not csv_file.name.endswith('.csv'):
                raise forms.ValidationError('Exporteu el fitxer .csv')
        return csv_file
