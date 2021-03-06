import os

from django import forms
from django.conf import settings
from django.core.validators import MinLengthValidator
from django.utils import timezone

from clones.forms import RNAiKnockdownField
from experiments.models import (Experiment, ExperimentPlate,
                                ManualScore, ManualScoreCode)
from library.forms import LibraryPlateField
from utils.forms import EMPTY_CHOICE, BlankNullBooleanSelect, RangeField
from worms.forms import (MutantKnockdownField, WormChoiceField,
                         clean_mutant_query_and_screen_type)
from worms.models import WormStrain

SCORE_DEFAULT_PER_PAGE = 50

SCREEN_STAGE_CHOICES = [
    (1, 'Primary'),
    (2, 'Secondary'),
]

SCREEN_TYPE_CHOICES = [
    ('SUP', 'Suppressor'),
    ('ENH', 'Enhancer'),
]

SCORING_FORM_CHOICES = [
    ('SUP', 'Suppressor scoring (w/m/s)'),
    ('LEVELS', 'Enhancer secondary (levels)'),
]

IMPOSSIBLE = 'impossible'


##########
# Fields #
##########

class ScreenStageChoiceField(forms.ChoiceField):
    """Field for choosing Primary, Secondary, etc."""

    def __init__(self, **kwargs):
        kwargs['choices'] = [EMPTY_CHOICE] + SCREEN_STAGE_CHOICES
        super(ScreenStageChoiceField, self).__init__(**kwargs)


class ScreenTypeChoiceField(forms.ChoiceField):
    """
    Field defining a screen as SUP or ENH.

    Whether an experiment is SUP/ENH is based on its worm strain's
    restrictive/permissive temperature.
    """

    def __init__(self, **kwargs):
        kwargs['choices'] = [(x, y.lower()) for x, y in SCREEN_TYPE_CHOICES]

        if 'widget' not in kwargs:
            kwargs['widget'] = forms.RadioSelect

        super(ScreenTypeChoiceField, self).__init__(**kwargs)


class ScreenTypeChoiceFieldWithEmpty(forms.ChoiceField):
    """
    Field defining a screen as SUP or ENH.

    Whether an experiment is SUP/ENH is based on its
    worm strain's restrictive/permissive temperature.
    """

    def __init__(self, **kwargs):
        kwargs['choices'] = [EMPTY_CHOICE] + SCREEN_TYPE_CHOICES
        super(ScreenTypeChoiceFieldWithEmpty, self).__init__(**kwargs)


class TemperatureChoiceField(forms.ChoiceField):
    """Field for selecting a tested temperature."""

    def __init__(self, **kwargs):
        temperatures = ExperimentPlate.get_tested_temperatures()
        kwargs['choices'] = [EMPTY_CHOICE] + [(x, x) for x in temperatures]
        super(TemperatureChoiceField, self).__init__(**kwargs)


class ScoringFormChoiceField(forms.ChoiceField):
    """Field for selecting which scoring form (buttons) should display."""

    def __init__(self, **kwargs):
        kwargs['choices'] = [EMPTY_CHOICE] + SCORING_FORM_CHOICES
        super(ScoringFormChoiceField, self).__init__(**kwargs)


class ScoringListChoiceField(forms.ChoiceField):

    def __init__(self, **kwargs):
        kwargs['choices'] = (
            [EMPTY_CHOICE] +
            [(x, x) for x in os.listdir(settings.BASE_DIR_SCORING_LISTS)]
        )
        super(ScoringListChoiceField, self).__init__(**kwargs)


class SingleScoreField(forms.TypedChoiceField):
    """Field for choosing a level of suppression.

    NOTE: avoid ModelChoiceField because there is no clean way to
    include an empty value (for the "unscorable" case) while still
    making the field required and while not setting an initial value.
    """

    def __init__(self, key, **kwargs):
        choices = []
        for code in ManualScoreCode.get_codes(key):
            choices.append((code.pk, str(code)))

        choices.append((IMPOSSIBLE, 'Impossible to judge'))
        kwargs['choices'] = choices

        kwargs['coerce'] = _coerce_to_manualscorecode

        if 'required' not in kwargs:
            kwargs['required'] = True

        if 'widget' not in kwargs:
            kwargs['widget'] = forms.RadioSelect(attrs={'class': 'keyable'})

        super(SingleScoreField, self).__init__(**kwargs)


class MultiScoreField(forms.ModelMultipleChoiceField):
    """Field for selecting auxiliary scores."""

    def __init__(self, key, **kwargs):
        kwargs['queryset'] = ManualScoreCode.get_codes(key)

        if 'widget' not in kwargs:
            kwargs['widget'] = forms.CheckboxSelectMultiple(
                attrs={'class': 'keyable'})

        super(MultiScoreField, self).__init__(**kwargs)


def _coerce_to_manualscorecode(value):
    if value == IMPOSSIBLE:
        return IMPOSSIBLE

    return ManualScoreCode.objects.get(pk=value)


##############
# Validators #
##############

def validate_new_experiment_plate_id(x):
    """Validate that x is a valid ID for a new experiment plate."""
    if x <= 0:
        raise forms.ValidationError('ExperimentPlate ID must be positive')

    if ExperimentPlate.objects.filter(pk=x).count():
        raise forms.ValidationError('ExperimentPlate ID {} already exists'
                                    .format(x))


###################
# Filtering Forms #
###################

class _FilterExperimentsBaseForm(forms.Form):
    """Base for FilterExperimentWellsForm, FilterExperimentPlatesForm, etc."""

    plate__pk = forms.IntegerField(
        required=False, label='Plate ID', help_text='e.g. 32412')

    plate__date = forms.DateField(
        required=False, label='Date', help_text='YYYY-MM-DD')

    '''
    NOTE: When the below field was a TemperatureChoiceField, it caused
    issues when calling ./manage.py subcommands on an empty database.

    (In case you're wonding, why was I calling ./manage.py on an empty
     database? It was to populate an empty database from scratch, by
     running `./manage.py migrate`).

    The error (which I saw both when trying to run `./manage.py migrate`
    and `./manage.py runserver`:

        django.db.utils.ProgrammingError: (1146, "Table
            'eegi.experimentplate' doesn't exist")

    This only causes an issue with Django >=1.9.0. Django 1.8.9 was
    fine. For now, just use a DecimalField instead.
    '''
    plate__temperature = forms.DecimalField(
        required=False, label='Temperature')

    plate__screen_stage = ScreenStageChoiceField(
        required=False, label='Screen stage')

    worm_strain = WormChoiceField(required=False)


class FilterExperimentPlatesForm(_FilterExperimentsBaseForm):
    """Form for filtering ExperimentPlate instances."""

    plate__pk__range = RangeField(
        forms.IntegerField, required=False, label='Plate ID range')

    plate__date__range = RangeField(
        forms.DateField, required=False, label='Date range')

    plate__temperature__range = RangeField(
        forms.DecimalField, required=False, label='Temperature range')

    library_stock__plate = LibraryPlateField(
        required=False, label='Library plate', help_text='e.g. II-3-B2')

    is_junk = forms.NullBooleanField(
        required=False, initial=None, label='Has junk',
        widget=BlankNullBooleanSelect)

    field_order = [
        'plate__pk', 'plate__pk__range',
        'plate__date',  'plate__date__range',
        'plate__screen_stage',
        'plate__temperature', 'plate__temperature__range',
        'worm_strain',
        'library_stock__plate', 'is_junk',
    ]

    def process(self):
        cleaned_data = self.cleaned_data
        _remove_empties_and_none(cleaned_data)
        plate_pks = (Experiment.objects.filter(**cleaned_data)
                     .order_by('plate').values_list('plate', flat=True))
        return ExperimentPlate.objects.filter(pk__in=plate_pks)


class FilterExperimentWellsForm(_FilterExperimentsBaseForm):
    """Form for filtering Experiment instances."""

    pk = forms.CharField(required=False, help_text='e.g. 32412_A01',
                         label='Experiment ID')

    screen_type = ScreenTypeChoiceFieldWithEmpty(required=False)

    library_stock = forms.CharField(
        required=False, help_text='e.g. I-3-B2_A01',
        widget=forms.TextInput(attrs={'size': '15'}))

    library_stock__intended_clone = forms.CharField(
        required=False, label='Intended clone', help_text='e.g. sjj_AH10.4',
        widget=forms.TextInput(attrs={'size': '15'}))

    is_junk = forms.NullBooleanField(
        required=False, initial=None, widget=BlankNullBooleanSelect)

    exclude_no_clone = forms.BooleanField(
        required=False, label='Exclude (supposedly) empty wells')

    exclude_l4440 = forms.BooleanField(
        required=False, label='Exclude L4440')

    field_order = [
        'pk', 'plate__pk', 'well', 'plate__date', 'plate__screen_stage',
        'screen_type', 'plate__temperature',
        'worm_strain', 'library_stock', 'library_stock__intended_clone',
        'exclude_no_clone', 'exclude_l4440', 'is_junk',
    ]

    def process(self):
        cleaned_data = self.cleaned_data

        exclude_no_clone = cleaned_data.pop('exclude_no_clone')
        exclude_l4440 = cleaned_data.pop('exclude_l4440')
        screen_type = cleaned_data.pop('screen_type')

        _remove_empties_and_none(cleaned_data)
        experiments = Experiment.objects.filter(**cleaned_data)

        if exclude_no_clone:
            experiments = experiments.exclude(
                library_stock__intended_clone__isnull=True)

        if exclude_l4440:
            experiments = experiments.exclude(
                library_stock__intended_clone='L4440')

        # Must be done last, since it post-processes the query
        if screen_type:
            experiments = _limit_to_screen_type(experiments, screen_type)

        return experiments


class FilterExperimentWellsToScoreForm(_FilterExperimentsBaseForm):
    """Form for filtering experiment wells to score."""

    score_form_key = ScoringFormChoiceField(label='Which buttons?')

    scoring_list = ScoringListChoiceField(required=False,
                                          label='Limit to file?')

    pk = forms.CharField(required=False, help_text='e.g. 32412_A01',
                         label='Experiment ID')

    screen_type = ScreenTypeChoiceFieldWithEmpty(required=False)

    is_junk = forms.NullBooleanField(
        required=False, initial=False, widget=BlankNullBooleanSelect)

    exclude_no_clone = forms.BooleanField(
        required=False, initial=True, label='Exclude (supposedly) empty wells')

    exclude_l4440 = forms.BooleanField(
        required=False, initial=True, label='Exclude L4440')

    images_per_page = forms.IntegerField(
        required=True, initial=SCORE_DEFAULT_PER_PAGE,
        widget=forms.TextInput(attrs={'size': '3'}))

    unscored_by_user = forms.BooleanField(
        required=False, initial=True,
        label='Exclude if already scored by you')

    randomize_order = forms.BooleanField(required=False, initial=True)

    field_order = [
        'score_form_key', 'scoring_list', 'images_per_page',
        'unscored_by_user',
        'randomize_order', 'exclude_l4440', 'exclude_no_clone', 'is_junk',
        'plate__screen_stage', 'plate__date', 'screen_type',
        'plate__temperature', 'worm_strain',
        'pk', 'plate__pk',
    ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(FilterExperimentWellsToScoreForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(FilterExperimentWellsToScoreForm, self).clean()
        if (cleaned_data.get('randomize_order') and
                not cleaned_data.get('unscored_by_user')):
            raise forms.ValidationError(
                'Randomizing order not currently supported when '
                'scoring images you have already scored.')
        return cleaned_data

    def process(self):
        cleaned_data = self.cleaned_data

        score_form_key = cleaned_data.pop('score_form_key')
        filename = cleaned_data.pop('scoring_list')
        images_per_page = cleaned_data.pop('images_per_page')
        exclude_no_clone = cleaned_data.pop('exclude_no_clone')
        exclude_l4440 = cleaned_data.pop('exclude_l4440')
        unscored_by_user = cleaned_data.pop('unscored_by_user')
        screen_type = cleaned_data.pop('screen_type')
        randomize_order = cleaned_data.pop('randomize_order')

        _remove_empties_and_none(cleaned_data)
        experiments = Experiment.objects.filter(**cleaned_data)

        if exclude_no_clone:
            experiments = experiments.exclude(
                library_stock__intended_clone__isnull=True)

        if exclude_l4440:
            experiments = experiments.exclude(
                library_stock__intended_clone='L4440')

        if unscored_by_user:
            score_ids = (
                ManualScore.objects
                .filter(experiment__in=experiments, scorer=self.user)
                .values_list('experiment_id', flat=True))
            experiments = experiments.exclude(id__in=score_ids)

        # Special case for Malcolm to score subset defined in a file
        if filename:
            path = os.path.join(settings.BASE_DIR_SCORING_LISTS, filename)

            with open(path, 'r') as f:
                key = f.readline().strip()
                scoring_list = [line.strip() for line in f]

                if key == 'library_stock':
                    experiments = experiments.filter(
                        library_stock__in=scoring_list)

        if randomize_order:
            # Warning: Django docs mentions that `order_by(?)` may be
            # expensive and slow. If performance becomes an issue, switch
            # to another way
            experiments = experiments.order_by('?')

        # Must be done last, since it post-processes the query
        if screen_type:
            experiments = _limit_to_screen_type(experiments, screen_type)

        return {
            'experiments': experiments,
            'score_form': get_score_form(score_form_key),
            'images_per_page': images_per_page,
            'unscored_by_user': unscored_by_user,
        }


def _remove_empties_and_none(d):
    """Remove key-value pairs from dictionary if the value is '' or None."""
    for k, v in d.items():
        # Retain 'False' as a legitimate filter
        if v is False:
            continue

        # Ditch empty strings and None as filters
        if not v:
            del d[k]


def _limit_to_screen_type(experiments, screen_type):
    '''
    Post-process experiments QuerySet such that each experiment was done at its
    worm's SUP or ENH temperature. Since N2 does not have a SUP or ENH
    temperature, N2 will not be in this result.

    Question: Why not just get the SUP/ENH temperature for these experiments'
    worm, and then using `.filter()` with that temperature?

    Answer: That is what I do on queries limited to a single worm strain, e.g.
    for most of the public-facing pages. But these experiment filtering forms
    are meant to be flexible (basically a gateway into the database for GI
    team use only), flexible enough to potentially include multiple strains
    with different SUP/ENH temperatures (e.g. maybe Noah wants to see all
    experiments from one date).

    Question: Why not just join between ExperimentPlate.temperature and
    WormStrain.permissive_temperature / .restrictive_temperature?

    This would involve joining WormStrain on a second field. While easy with
    raw SQL, this is not easy with Django, requiring either 1) soon-to-
    be-deprecated `empty()`, 2) overriding low level query processing in ways
    that are subject to syntax changes, or 3) using `raw()` to write raw SQL.
    While I was tempted to do 3), since these filtering forms are meant to be
    generic and applicable (able to take dozens of possible keys to filter on),
    this one case doesn't warrant losing the readability and protections
    against SQL injection attacks that Django QuerySets provide.
    '''
    # Create a dictionary
    to_temperature = WormStrain.get_worm_to_temperature_dictionary(screen_type)
    filtered = []

    for experiment in experiments.prefetch_related('worm_strain', 'plate'):
        temperature = experiment.plate.temperature

        if temperature == to_temperature[experiment.worm_strain]:
            filtered.append(experiment)

    return filtered


###################
# Knockdown forms #
###################

class RNAiKnockdownForm(forms.Form):
    """Form for finding wildtype worms tested with a single RNAi clone."""

    rnai_query = RNAiKnockdownField(
        label='RNAi query',
        validators=[MinLengthValidator(1, message='No clone match')])

    temperature = forms.DecimalField(required=False, label='Temperature',
                                     help_text='optional')


class MutantKnockdownForm(forms.Form):
    """Form for finding a mutant worm with the control bacteria."""

    mutant_query = MutantKnockdownField()
    screen_type = ScreenTypeChoiceField()

    def clean(self):
        cleaned_data = super(MutantKnockdownForm, self).clean()
        cleaned_data = clean_mutant_query_and_screen_type(self, cleaned_data)
        return cleaned_data


class DoubleKnockdownForm(forms.Form):
    """Form for finding a double knockdown."""

    mutant_query = MutantKnockdownField()
    rnai_query = RNAiKnockdownField(
        label='RNAi query',
        validators=[MinLengthValidator(1, message='No clone matches')])
    screen_type = ScreenTypeChoiceField()

    def clean(self):
        cleaned_data = super(DoubleKnockdownForm, self).clean()
        cleaned_data = clean_mutant_query_and_screen_type(self, cleaned_data)
        return cleaned_data


##########################
# Secondary Scores forms #
##########################

class SecondaryScoresForm(forms.Form):
    """Form for getting all secondary scores for a worm/screen combo."""

    mutant_query = MutantKnockdownField()
    screen_type = ScreenTypeChoiceField()

    def clean(self):
        cleaned_data = super(SecondaryScoresForm, self).clean()
        cleaned_data = clean_mutant_query_and_screen_type(self, cleaned_data)
        return cleaned_data


#################
# Scoring Forms #
#################

def get_score_form(key):
    d = {
        'SUP': SuppressorScoreForm,
        'LEVELS': LevelsScoreForm,
    }
    return d[key]


class ScoreForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ScoreForm, self).__init__(*args, **kwargs)


class SuppressorScoreForm(ScoreForm):

    sup_score = SingleScoreField(key='SUP', required=True)
    auxiliary_scores = MultiScoreField(key='AUXILIARY', required=False)

    def clean(self):
        cleaned_data = super(SuppressorScoreForm, self).clean()

        if ('sup_score' in cleaned_data and
                cleaned_data['sup_score'] == IMPOSSIBLE and
                not cleaned_data['auxiliary_scores']):
            raise forms.ValidationError('"Impossible to judge" requires '
                                        'some auxiliary score')
        return cleaned_data

    def process(self):
        cleaned_data = self.cleaned_data
        save_score = _get_save_score(self)

        save_score(cleaned_data.get('sup_score'))

        for code in cleaned_data.get('auxiliary_scores'):
            save_score(code)


class LevelsScoreForm(ScoreForm):

    emb_score = SingleScoreField(key='EMB_LEVEL', required=True)
    ste_score = SingleScoreField(key='STE_LEVEL', required=True)
    auxiliary_scores = MultiScoreField(key='AUXILIARY', required=False)

    def clean(self):
        cleaned_data = super(LevelsScoreForm, self).clean()

        if ('emb_score' in cleaned_data and 'ste_score' in cleaned_data and
                cleaned_data['emb_score'] == IMPOSSIBLE and
                cleaned_data['ste_score'] == IMPOSSIBLE and
                not cleaned_data['auxiliary_scores']):
            raise forms.ValidationError('"Impossible to judge" requires '
                                        'some auxiliary score')
        return cleaned_data

    def process(self):
        cleaned_data = self.cleaned_data
        save_score = _get_save_score(self)

        save_score(cleaned_data.get('emb_score'))
        save_score(cleaned_data.get('ste_score'))

        for code in cleaned_data.get('auxiliary_scores'):
            save_score(code)


def _get_save_score(form):
    experiment = Experiment.objects.get(pk=form.prefix)

    # Each simultaneously-scored score for this image should get the same
    # timestamp
    time = timezone.now()

    def save_score(score_code):
        if score_code == IMPOSSIBLE:
            return

        score = ManualScore(
            experiment=experiment, score_code=score_code,
            scorer=form.user, timestamp=time)
        score.save()

    return save_score


##################################
# Other database-modifying forms #
##################################

class AddExperimentPlateForm(forms.Form):
    """
    Form for adding a new experiment plate.

    Adding a new experiment plate also adds the corresponding
    experiment wells.

    This form makes certain assumptions about the experiment plate:
        - it comes from one library plate
        - it has same worm strain in every well
        - the whole plate is or is not junk
    """

    experiment_plate_id = forms.IntegerField(
        required=True,
        validators=[validate_new_experiment_plate_id])
    screen_stage = ScreenStageChoiceField(required=True)
    date = forms.DateField(required=True, help_text='YYYY-MM-DD')
    temperature = forms.DecimalField(required=True)
    worm_strain = WormChoiceField(required=True)
    library_plate = LibraryPlateField(required=True)
    is_junk = forms.BooleanField(initial=False, required=False)
    plate_comment = forms.CharField(required=False)


class ChangeExperimentPlatesForm(forms.Form):
    """
    Form for updating multiple experiment plates.

    Depending on what field(s) are being updated, the corresponding
    experiment wells might be updated as well.

    Keep in mind the following assumptions that will apply if
    updating one of the following fields:
        - each experiment plate comes from one library plate
        - each experiment plate has only one worm strain
        - each experiment plate is or is not junk
    """

    # Plate-level fields
    screen_stage = ScreenStageChoiceField(required=False)
    date = forms.DateField(required=False, help_text='YYYY-MM-DD')
    temperature = forms.DecimalField(required=False)
    comment = forms.CharField(required=False, label='Plate comment')

    # Well-level fields
    worm_strain = WormChoiceField(required=False)
    is_junk = forms.NullBooleanField(
        required=False, initial=None, widget=BlankNullBooleanSelect)

    # Other
    library_plate = LibraryPlateField(required=False)
    clear_plate_comment = forms.BooleanField(required=False)

    field_order = [
        'screen_stage', 'date', 'temperature', 'worm_strain',
        'library_plate', 'is_junk', 'plate_comment', 'well_comment']


def process_ChangeExperimentPlatesForm_data(experiment_plate, data):
    """
    Helper to apply the ChangeExperimentPlateForm changes to a specific
    plate.

    data should be the cleaned_data from a ChangeExperimentPlatesForm.
    """
    # First update straightforward plate fields
    for key in ('screen_stage', 'date', 'temperature', 'comment',):
        value = data.get(key)

        if value:
            setattr(experiment_plate, key, value)
            experiment_plate.save()

    # Next update plate methods
    if data.get('worm_strain'):
        experiment_plate.set_worm_strain(data.get('worm_strain'))

    if data.get('library_plate'):
        experiment_plate.set_library_stocks(data.get('library_plate'))

    if data.get('is_junk') is not None:
        experiment_plate.set_junk(data.get('is_junk'))

    return
