# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-07-30 02:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('worms', '0002_auto_20160112_0853'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wormstrain',
            name='genotype',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
