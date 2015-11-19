from __future__ import division
from collections import OrderedDict

from django.shortcuts import render, redirect, get_object_or_404

from experiments.forms import SecondaryScoresForm

from experiments.helpers.criteria import (
    passes_sup_positive_percentage_criteria,
    passes_sup_positive_count_criteria,
    passes_sup_stringent_criteria)

from experiments.helpers.scores import get_average_score_weight

from worms.models import WormStrain


def secondary_scores(request, worm, temperature):
    """Render the page to display secondary scores for a mutant/screen.

    Results show strongest positives on top.

    """
    worm = get_object_or_404(WormStrain, pk=worm)
    screen = worm.get_screen_category(temperature)

    num_passes_stringent = 0
    num_passes_percentage = 0
    num_passes_count = 0
    num_experiment_columns = 0

    data = worm.get_organized_scores(screen, screen_stage=2,
                                     most_relevant_only=True)

    for well, expts in data.iteritems():
        scores = expts.values()
        well.avg = get_average_score_weight(scores)

        well.passes_stringent = passes_sup_stringent_criteria(scores)
        well.passes_percentage = passes_sup_positive_percentage_criteria(
            scores)
        well.passes_count = passes_sup_positive_count_criteria(scores)

        if well.passes_stringent:
            num_passes_stringent += 1

        if well.passes_percentage:
            num_passes_percentage += 1

        if well.passes_count:
            num_passes_count += 1

        if len(expts) > num_experiment_columns:
            num_experiment_columns = len(expts)

    data = OrderedDict(sorted(
        data.iteritems(),
        key=lambda x: (x[0].passes_stringent,
                       x[0].passes_percentage,
                       x[0].passes_count,
                       x[0].avg),
        reverse=True))

    context = {
        'worm': worm,
        'screen': screen,
        'temperature': temperature,
        'data': data,
        'num_wells': len(data),
        'num_passes_percentage': num_passes_percentage,
        'num_passes_count': num_passes_count,
        'num_passes_stringent': num_passes_stringent,
        'num_experiment_columns': num_experiment_columns,
    }

    return render(request, 'secondary_scores.html', context)


def secondary_scores_search(request):
    """Render the page to find secondary scores for a mutant/screen."""
    if request.method == 'POST':
        form = SecondaryScoresForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            worm = data['worm']
            temperature = data['temperature']
            return redirect(secondary_scores, worm, temperature)

    else:
        form = SecondaryScoresForm(initial={'screen': 'SUP'})

    context = {
        'form': form,
    }

    return render(request, 'secondary_scores_search.html', context)
