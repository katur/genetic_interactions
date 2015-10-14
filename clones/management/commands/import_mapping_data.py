import MySQLdb

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from clones.models import Clone, Gene, CloneTarget
from eegi.local_settings import MAPPING_DATABASE
from utils.db import get_field_dictionary
from utils.scripting import require_db_write_acknowledgement

HELP = '''Import clone data from Firoz's RNAiCloneMapper database.'''


class Command(BaseCommand):
    help = HELP

    def handle(self, **options):
        require_db_write_acknowledgement()

        mapping_db = MySQLdb.connect(host=MAPPING_DATABASE['HOST'],
                                     user=MAPPING_DATABASE['USER'],
                                     passwd=MAPPING_DATABASE['PASSWORD'],
                                     db=MAPPING_DATABASE['NAME'])

        self.cursor = mapping_db.cursor()

        self.mapping_alias_to_pk = self.get_mapping_alias_to_pk()
        self.mapping_clones = self.get_mapping_clones()
        self.mapping_genes = self.get_mapping_genes()
        self.mapping_targets = self.get_mapping_targets()

        self.number_clones_no_targets = 0
        self.number_clones_multiple_targets = 0

        clones = Clone.objects.all()

        for clone in clones:
            self.process_clone(clone)

        self.stdout.write('{} clones with no targets.'
                          .format(self.number_clones_no_targets))
        self.stdout.write('{} clones with multiple targets.'
                          .format(self.number_clones_multiple_targets))

    def get_mapping_alias_to_pk(self):
        """Get a dictionary to translate mapping_alias to mapping_pk."""
        query = 'SELECT alias, clone_id FROM CloneAlias'

        self.cursor.execute(query)

        rows = self.cursor.fetchall()

        mapping_alias_to_pk = {}

        for row in rows:
            alias, mapping_pk = row
            if alias not in mapping_alias_to_pk:
                mapping_alias_to_pk[alias] = []

            if mapping_pk not in mapping_alias_to_pk[alias]:
                mapping_alias_to_pk[alias].append(mapping_pk)

        return mapping_alias_to_pk

    def get_mapping_clones(self):
        """Get dictionary of all clones from the mapping database.

        This dictionary is keyed on the clone's pk in the mapping
        database.

        The value is a dictionary of fieldname:value pairs in the
        mapping database.

        """
        fieldnames = ['id', 'library', 'clone_type', 'forward_primer',
                      'reverse_primer']
        return get_field_dictionary(self.cursor, 'Clone', fieldnames)

    def get_mapping_genes(self):
        """Get dictionary of all genes from the mapping database.

        This dictionary is keyed on the gene's pk in the mapping
        database.

        The value is a dictionary of fieldname:value pairs in the
        mapping database.

        """
        fieldnames = ['id', 'cosmid_id', 'locus', 'gene_type']
        return get_field_dictionary(self.cursor, 'Gene', fieldnames)

    def get_mapping_targets(self):
        """Get dictionary of all targets from the mapping database.

        This dictionary is keyed on the clone's pk in the mapping database.

        The value is a list. Each item in this list is a dictionary
        capturing the fieldname:value pairs about one target of this clone.

        """
        fieldnames = [
            'clone_id', 'id', 'clone_amplicon_id',
            'amplicon_evidence', 'amplicon_is_designed',
            'amplicon_is_unique',
            'gene_id', 'transcript_isoform',
            'length_span', 'raw_score', 'unique_raw_score',
            'relative_score', 'specificity_index', 'unique_chunk_index',
            'is_on_target', 'is_primary_target'
        ]
        fieldnames_as_string = ', '.join(fieldnames)
        query = 'SELECT {} FROM CloneTarget'.format(fieldnames_as_string)
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        all_targets = {}
        for row in rows:
            clone_pk = row[0]
            if clone_pk not in all_targets:
                all_targets[clone_pk] = []

            this_target = {}
            for k, v in zip(fieldnames[1:], row[1:]):
                this_target[k] = v

            all_targets[clone_pk].append(this_target)

        return all_targets

    def process_clone(self, clone):
        """Do all processing for this clone, both its info and targets."""
        if clone.pk == 'L4440':
            return

        if clone.pk not in self.mapping_alias_to_pk:
            raise CommandError('No alias match for {}'.format(clone.pk))

        mapping_pks = self.mapping_alias_to_pk[clone.pk]

        if len(mapping_pks) > 1:
            raise CommandError('>1 alias match for {}'.format(clone.pk))

        clone.mapping_db_pk = mapping_pks[0]

        self.update_clone_info(clone)
        self.update_clone_targets(clone)

    def update_clone_targets(self, clone):
        """Do all processing for this clone's targets."""
        try:
            mapping_targets = self.mapping_targets[clone.mapping_db_pk]
        except KeyError:
            self.stdout.write('Clone {} has no targets'.format(clone))
            self.number_clones_no_targets += 1
            return

        if len(mapping_targets) > 1:
            self.number_clones_multiple_targets += 1

        for target_info in mapping_targets:
            gene_id = target_info['gene_id']

            try:
                gene = Gene.objects.get(pk=gene_id)
            except ObjectDoesNotExist:
                if gene_id in self.mapping_genes:
                    gene = Gene(id=gene_id)
                else:
                    self.stdout.write('Gene {} from targets table not present '
                                      'in gene table'.format(gene_id))
                    continue

            self.update_gene_info(gene)

            target_id = target_info['id']

            try:
                target = CloneTarget.objects.get(pk=target_id)
            except ObjectDoesNotExist:
                target = CloneTarget(id=target_id)

            self.update_target_info(target, clone, gene, target_info)

    def update_clone_info(self, clone):
        clone_info = self.mapping_clones[clone.mapping_db_pk]
        clone.library = clone_info['library']
        clone.clone_type = clone_info['clone_type']
        clone.forward_primer = clone_info['forward_primer']
        clone.reverse_primer = clone_info['reverse_primer']
        clone.save()

    def update_gene_info(self, gene):
        gene_info = self.mapping_genes[gene.id]
        gene.cosmid_id = gene_info['cosmid_id']
        gene.locus = gene_info['locus']
        if gene.locus == 'NA':
            gene.locus = ''
        gene.gene_type = gene_info['gene_type']
        gene.save()

    def update_target_info(self, target, clone, gene, target_info):
        target.clone = clone
        target.gene = gene
        target.clone_amplicon_id = target_info['clone_amplicon_id']
        target.amplicon_evidence = target_info['amplicon_evidence']
        target.amplicon_is_designed = target_info['amplicon_is_designed']
        target.amplicon_is_unique = target_info['amplicon_is_unique']
        target.transcript_isoform = target_info['transcript_isoform']
        target.length_span = target_info['length_span']
        target.raw_score = target_info['raw_score']
        target.unique_raw_score = target_info['unique_raw_score']
        target.relative_score = target_info['relative_score']
        target.specificity_index = target_info['specificity_index']
        target.unique_chunk_index = target_info['unique_chunk_index']
        target.is_on_target = target_info['is_on_target']
        target.is_primary_target = target_info['is_primary_target']
        target.save()