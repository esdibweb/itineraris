from django.db import models


class CourseYear(models.Model):
    year = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.year


class Expedient(models.Model):
    """A student's academic file. A student has one file per programme they enrol in."""
    number = models.IntegerField(unique=True)
    # SET_NULL: deleting a student keeps the file and its enrolments
    student = models.ForeignKey(
        'Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='expedients',
    )

    def __str__(self):
        return str(self.number)


class Matricula(models.Model):
    course_year = models.ForeignKey(CourseYear, on_delete=models.CASCADE)
    expedient = models.ForeignKey(Expedient, on_delete=models.CASCADE)
    data = models.DateTimeField(null=True, blank=True)
    pla_estudis = models.CharField(max_length=255, null=True)
    caracter = models.CharField(max_length=100, null=True)
    credits = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    total_credits = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    estudis = models.CharField(max_length=255, null=True)
    especialitat = models.CharField(max_length=255, null=True)
    curs = models.CharField(max_length=100, null=True)
    periode = models.CharField(max_length=100, null=True)
    assignatura = models.CharField(max_length=255, null=True)
    iteracio = models.CharField(max_length=100, null=True)
    reconeixements = models.CharField(max_length=255, null=True)
    grup = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.expedient.__str__() + ' - ' + self.course_year.year


class Student(models.Model):
    type_id = models.CharField(max_length=100)
    id_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    second_name = models.CharField(max_length=100, null=True)
    complete_name = models.CharField(max_length=200, null=True)
    phone = models.CharField(max_length=100, null=True)
    mobile = models.CharField(max_length=100, null=True)
    birthday = models.DateField(null=True)
    email = models.EmailField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=100, null=True)
    province = models.CharField(max_length=100, null=True)
    region = models.CharField(max_length=100, null=True)
    postal_code = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    school_email = models.EmailField(max_length=100, null=True)
    desired_name = models.CharField(max_length=100)

    class Meta:
        ordering = ['complete_name']
        permissions = (
            ('import_codex_info', 'Importar dades del Codex'),
        )

    def __str__(self):
        surnames = ' '.join(filter(None, [self.first_name, self.second_name]))
        return f'{surnames}, {self.name}'


class Teacher(models.Model):
    type_id = models.CharField(max_length=100)
    id_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    second_name = models.CharField(max_length=100, null=True)
    phone = models.CharField(max_length=100, null=True)
    mobile = models.CharField(max_length=100, null=True)
    birthday = models.DateField(null=True)
    email = models.EmailField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=100, null=True)
    province = models.CharField(max_length=100, null=True)
    region = models.CharField(max_length=100, null=True)
    postal_code = models.CharField(max_length=100, null=True)
    address = models.CharField(max_length=100, null=True)
    school_email = models.EmailField(max_length=100, null=True)
    course_years = models.ManyToManyField(CourseYear)
    complete_name = models.CharField(max_length=200, null=True)

    class Meta:
        ordering = ['complete_name']

    def __str__(self):
        surnames = ' '.join(filter(None, [self.first_name, self.second_name]))
        return f'{surnames}, {self.name}'
