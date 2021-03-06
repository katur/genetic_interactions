from decimal import Decimal

from django.db import models

from library.models import LibraryStock


class WormStrain(models.Model):
    """
    A worm strain used in the screen.

    Can be either a temperature-sensitive mutant strain, or a control
    strain. Control strains are signified by allele=None.
    """

    # The name of this strain (e.g. KK300)
    id = models.CharField(max_length=10, primary_key=True)

    # Gene and allele causing temperature-sensitivity in this strain
    gene = models.CharField(max_length=10, blank=True)
    allele = models.CharField(max_length=10, blank=True)
    genotype = models.CharField(max_length=50, blank=True)

    # Temperatures, in Celsius, used for screening
    permissive_temperature = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True)
    restrictive_temperature = models.DecimalField(
        max_digits=3, decimal_places=1, null=True, blank=True)

    class Meta:
        db_table = 'WormStrain'
        ordering = ['genotype']

    def __unicode__(self):
        return self.get_display_string()

    def __cmp__(self, other):
        if hasattr(other, 'genotype'):
            return cmp(self.genotype, other.genotype)
        else:
            return cmp(self.genotype, str(other))

    def get_display_string(self):
        if self.genotype:
            return '{}: {}'.format(self.id, self.get_short_genotype())
        else:
            return self.id

    def get_short_genotype(self):
        # Split out individual mutations
        parts = self.genotype.split(';')

        # Remove roman numeral if it exists
        parts = [part.split()[0] for part in parts]
        return '; '.join(parts)

    def get_url(self):
        return self.get_wormbase_url()

    def get_wormbase_url(self):
        return 'http://www.wormbase.org/species/c_elegans/strain/' + self.id

    def get_lab_website_url(self):
        return 'http://gunsaluspiano.bio.nyu.edu/strain/' + self.id

    def is_control(self):
        return not self.allele

    def is_permissive_temperature(self, temperature):
        return self.permissive_temperature == Decimal(temperature)

    def is_restrictive_temperature(self, temperature):
        return self.restrictive_temperature == Decimal(temperature)

    def get_screen_type(self, temperature):
        """
        Determine if temperature is a screening temperature for this worm.

        Returns 'ENH' if temperature is this strain's permissive
        screening temperature.

        Returns 'SUP' if temperature is this strain's restrictive
        screening temperature.

        Returns None if temperature is not an official screening
        temperature for this strain.
        """
        if self.is_permissive_temperature(temperature):
            return 'ENH'
        elif self.is_restrictive_temperature(temperature):
            return 'SUP'
        else:
            return None

    def get_organized_scores(self, screen_type, screen_stage,
                             most_relevant_only=False, **filters):
        """
        Get all scores for this worm in a particular screen.

        The screen is defined by both screen_type ('ENH' or 'SUP')
        and screen_stage (1 for primary, 2 for secondary).

        The data returned is organized as:
            data[library_stock][experiment] = [scores]

        Or, if most_relevant_only is set to True:
            data[library_stock][experiment] = most_relevant_score
        """
        # Import here to avoid creating a circular dependency
        from experiments.models import ManualScore
        scores = ManualScore.objects.filter(
            experiment__worm_strain=self,
            experiment__is_junk=False,
            experiment__plate__screen_stage=screen_stage,
            **filters)

        if screen_type == 'ENH':
            scores = scores.filter(
                experiment__plate__temperature=self.permissive_temperature)

        elif screen_type == 'SUP':
            scores = scores.filter(
                experiment__plate__temperature=self.restrictive_temperature)

        scores = (
            scores
            .select_related(
                'score_code', 'scorer',
                'experiment', 'experiment__plate',
                'experiment__library_stock',
                'experiment__library_stock__intended_clone')
            .prefetch_related(
                'experiment__library_stock__intended_clone__'
                'clonetarget_set',
                'experiment__library_stock__intended_clone__'
                'clonetarget_set__gene')
            .order_by('experiment'))

        from experiments.helpers.scores import organize_manual_scores
        return organize_manual_scores(scores, most_relevant_only)

    def get_positives(self, screen_type, screen_stage, criteria, **kwargs):
        """
        Get stocks that meet criteria for this worm in a particular screen.

        The screen is defined by both screen_type ('ENH' or 'SUP')
        and screen_stage (1 for primary, 2 for secondary).
        """
        s = self.get_organized_scores(screen_type, screen_stage,
                                      most_relevant_only=True)

        positives = set()

        for library_stock, experiments in s.iteritems():
            scores = experiments.values()
            if criteria(scores, **kwargs):
                positives.add(library_stock)

        return positives

    def get_experiments_by_screen(self, screen_type, screen_stage):
        """
        Get all experiments for this worm in a particular screen.

        The screen is defined by both screen_type ('ENH' or 'SUP')
        and screen_stage (1 for primary, 2 for secondary).
        """
        from experiments.models import Experiment
        prefix = Experiment.objects.filter(
            is_junk=False, worm_strain=self,
            plate__screen_stage=screen_stage)

        if screen_type == 'SUP':
            return prefix.filter(
                plate__temperature=self.restrictive_temperature)
        else:
            return prefix.filter(
                plate__temperature=self.permissive_temperature)

    def get_stocks_tested_by_number_of_replicates(
            self, screen_type, screen_stage, number_of_replicates):
        """
        Get stocks tested a specific number of times for this worm.

        Returns the stocks that were tested *exactly* number_of_replicates
        times in a particular screen.

        The screen is defined by both screen_type ('ENH' or 'SUP')
        and screen_stage (1 for primary, 2 for secondary).
        """
        annotated = (
            self.get_experiments_by_screen(screen_type, screen_stage)
            .order_by('library_stock')
            .values('library_stock')
            .annotate(models.Count('id')))

        singles_pks = [x['library_stock'] for x in annotated
                       if x['id__count'] == number_of_replicates]

        singles = LibraryStock.objects.filter(pk__in=singles_pks)

        return set(singles)

    @classmethod
    def get_n2(cls):
        """Get the N2 control worm strain."""
        return cls.objects.get(pk='N2')

    @classmethod
    def get_worms_for_screen_type(cls, screen_type):
        """
        Get the worm strains involved in a particular screen.

        screen_type must be 'ENH' or 'SUP'.
        """
        if screen_type not in {'ENH', 'SUP'}:
            raise Exception('screen_type must be ENH or SUP')

        worms = cls.objects

        if screen_type == 'ENH':
            return worms.exclude(permissive_temperature__isnull=True)
        else:
            return worms.exclude(restrictive_temperature__isnull=True)

    @classmethod
    def get_worm_and_temperature_from_search_term(cls, search_term,
                                                  screen_type):
        """
        Get tuple (worm, temperature) matching search_term and screen_type.

        screen_type must be 'ENH' or 'SUP'; otherwise an exception is thrown.

        search_term can be the allele, gene, or name of a worm strain.

        The combination of search_term + screen_type must uniquely identify a
        worm strain. Otherwise an exception is thrown.
        """
        worms = cls.get_worms_for_screen_type(screen_type)

        # TODO: fix this one-off workaround for the new emb-8 strains!!!
        if search_term == 'emb-8' or search_term == 'hc69':
            search_term = 'MJ69'

        worms = worms.filter(models.Q(gene=search_term) |
                             models.Q(allele=search_term) |
                             models.Q(pk=search_term))

        if not worms:
            return None
        elif len(worms) > 1:
            raise Exception('Multiple worm strains match search_term.')
        else:
            worm = worms.first()

        if screen_type == 'ENH':
            temperature = worm.permissive_temperature
        else:
            temperature = worm.restrictive_temperature

        return (worm, temperature)

    @classmethod
    def get_worm_to_temperature_dictionary(cls, screen_type):
        worms = cls.objects.all()
        to_temperature = {}

        for worm in worms:
            if screen_type == 'ENH':
                to_temperature[worm] = worm.permissive_temperature

            elif screen_type == 'SUP':
                to_temperature[worm] = worm.restrictive_temperature

        return to_temperature
