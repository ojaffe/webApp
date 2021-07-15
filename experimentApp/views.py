from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from utils import sortInputFiles, generateUniqueSlug, sortInputDirs
from .models import Experiment, ExperimentQuestion, Pairwise, PairwiseGroundTruth, Ranking, RankingChoice, Rating, \
    RatingChoice, ExperimentRegister, PairwiseChoice, RankingGroundTruth, RatingGroundTruth, ExperimentRefresher, \
    ExperimentSlug, ExperimentCustomColours
from .forms import ExperimentForm, OrderingForm

from PIL import Image

import random
import csv


# Homepage of website, "default" view, can navigate to everywhere from this
def index(request):
    latest_experiment_list = Experiment.objects.order_by('-pub_date')[:5]

    # Construct dict of experiment names and their respective slug, sorted by above date
    experiment_dict = {}
    for index, experiment in enumerate(latest_experiment_list):
        experiment_dict[index] = {'title': experiment.experiment_title, 'slug': get_object_or_404(ExperimentSlug, experiment=experiment).slug}

    return render(request, 'experimentApp/index.html', {'experiment_dict': experiment_dict})


# View used for presenting caught errors or handling redirects
def stageView(request):
    return render(request, 'experimentApp/stageView.html')


# View of documentation
def helpView(request):
    return render(request, 'experimentApp/helpView.html')


# View of summary about such website
def aboutView(request):
    return render(request, 'experimentApp/about.html')


# View containing table of all previous experiments, s.t. user can access, delete or view results for any of them
@login_required
def previousExperimentView(request):
    experiment_list = Experiment.objects.order_by('-pub_date')

    # Construct dict of experiment names and their respective slug, sorted by above date
    experiment_dict = {}
    for index, experiment in enumerate(experiment_list):
        experiment_dict[index] = {'title': experiment.experiment_title,
                                  'slug': get_object_or_404(ExperimentSlug, experiment=experiment).slug,
                                  'question_type': experiment.question_type,
                                  'pub_date': experiment.pub_date}

    return render(request, 'experimentApp/previousExperimentView.html', {'experiment_dict': experiment_dict})


# Renders experiment creation on GET request. POST requests after creating experiment should be redirected to other
# view, alert user if not
@login_required
def createExperiment(request):
    if request.method == 'GET':
        experimentForm = ExperimentForm()
        return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm})
    elif request.method == 'POST':
        experimentFullForm = ExperimentForm(request.POST or None)

        # If data and options chosen by user are valid
        if experimentFullForm.is_valid():

            # Redirect to helper function depending on type of questions
            question_type = request.POST.get("questionType")
            if question_type == "pc":
                return createExperimentPC(request)
            elif question_type == "rk":
                return createExperimentRK(request)
            elif question_type == "rt":
                return createExperimentRT(request)
        else:

            # Otherwise render same view with appropriate error message
            experimentForm = ExperimentForm()
            return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                               'error_message': 'Please enter a valid '
                                                                                                'title and description'})

    else:
        return render(request, 'experimentApp/stageView.html', {'title': 'Error',
                                                                'status_message': 'Error on requesting view: wrong'
                                                                                  ' request method. Please attempt to create an'
                                                                                  ' experiment again by navigating to home.'})


# View to create pairwise-comparison experiment on POST request from experiment creation. Creates respective models
# depending on options the user specified
@login_required
def createExperimentPC(request):
    if request.method == 'POST':
        experimentForm = ExperimentForm(request.POST)

        experimentFullForm = ExperimentForm(request.POST or None)

        if experimentFullForm.is_valid():

            # Save Experiment model
            experimentInstance = experimentForm.save(commit=False)
            experimentInstance.question_type = 'pairwise-comparison'
            experimentInstance.save()

            # Generates and saves experiment slug
            experimentSlug = generateUniqueSlug()
            ExperimentSlug.objects.create(experiment=experimentInstance, slug=experimentSlug)

            # Save custom colour options
            if request.POST.get("customColours"):
                ExperimentCustomColours.objects.create(experiment=experimentInstance,
                                                       text_colour=request.POST.get("textColourPicker"),
                                                       background_colour=request.POST.get("backgroundColourPicker"))

            # Save refresher options
            if request.POST.get("radRef"):
                time_shown = request.POST.get("timeVal")
                if request.POST.get("refChoice") == "col":
                    custom_colour = request.POST.get("colourpicker")
                    experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                              time_shown=time_shown, custom_colour=custom_colour,
                                                              custom_image=None)
                    experimentRefresher.save()
                else:
                    custom_image = request.FILES.get("refImage")
                    if custom_image is not None:
                        experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                                  time_shown=time_shown, custom_colour="",
                                                                  custom_image=custom_image)
                        experimentRefresher.save()
                    else:
                        return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                                       'error_message': 'Please upload '
                                                                                                        'a refresher image'})

            # Sorts list of files into list of list(s), where each sublist contains files with same suffix
            if request.POST.get("uploadChoice") == "file":
                files = request.FILES.getlist('uploadFileName')
                sorted_files = sortInputFiles(files, [])
            else:
                sorted_files = sortInputDirs(request)

            # Check each image set has consistent resolution
            for file_set in sorted_files:
                res = None
                for file in file_set:

                    im = Image.open(file)
                    if res is None:
                        res = im.size
                    elif res != im.size:
                        return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                                       'error_message': 'Please '
                                                                                                        'upload file '
                                                                                                        'sets with '
                                                                                                        'consistent '
                                                                                                        'resolutions'})

            # Randomise ordering if user chose
            if request.POST.get("pcRandomise"):
                random.shuffle(sorted_files)  # Randomises order of list

            # If user has chosen to compare same image from different algorithms
            algor_choice = request.POST['pcAlgorChoice']
            if algor_choice == "pcSameAlgor":

                question_counter = 1
                for file_set in sorted_files:

                    question = ExperimentQuestion(question_num=question_counter,
                                                  question_text='Question ' + str(question_counter),
                                                  experiment=experimentInstance)
                    question.save()
                    question_counter += 1

                    # Separate counter used for choices, so when ground-truth enabled it isn't included
                    choice_counter = 0

                    # If user wants chance of comparing the same image
                    if (request.POST.get("pcCompareWithSame") == "on") and random.uniform(0, 1) < 0.05:
                        algorithm_name = file_set[0].name.split('_', 1)[1]  # Gets name of file after first '_'
                        algorithm_name = algorithm_name.split('.')[0]  # Removes file extension
                        for file in file_set:

                            if (request.POST.get("pcGround") == "on") and ("input" in file.name):
                                PairwiseGroundTruth.objects.create(question=question,
                                                                   choice_text="Ground Truth", choice_image=file_set[0])
                            else:
                                Pairwise.objects.create(question=question, choice_algorithm=algorithm_name,
                                                        choice_text="Choice " + str(choice_counter),
                                                        choice_image=file_set[0])
                                choice_counter += 1

                    else:  # Otherwise add all images to question, ground truth exists in separate model if required
                        for file in file_set:
                            algorithm_name = file.name.split('_', 1)[1]  # Gets name of file after first '_'
                            algorithm_name = algorithm_name.split('.')[0]  # Removes file extension
                            if (request.POST.get("pcGround") == "on") and ("input" in file.name):
                                PairwiseGroundTruth.objects.create(question=question,
                                                                   choice_text="Ground Truth", choice_image=file)
                            else:
                                Pairwise.objects.create(question=question, choice_algorithm=algorithm_name,
                                                        choice_text="Choice " + str(choice_counter), choice_image=file)
                                choice_counter += 1

                return HttpResponseRedirect(reverse('experimentApp:experimentDetail', args=(experimentSlug,)))

            else:
                # For each set of files from same original image, generate all comparisons as questions
                question_counter = 1
                for file_set in sorted_files:

                    # Generate list of tuples of indexes of images which need to be compared, whilst not adding any
                    # ground truth images to the comparisons if the user requested so
                    comparisons_list = []
                    for i in range(len(file_set)):
                        if (request.POST.get("pcGround") == "on") and "input" in file_set[i].name:
                            continue

                        for j in range(i + 1, len(file_set)):
                            if (request.POST.get("pcGround") == "on") and "input" in file_set[j].name:
                                continue

                            # Else add pair to comparisons
                            comparisons_list.append((i, j))

                    if request.POST.get("pcRandomise"):
                        random.shuffle(comparisons_list)  # Randomises order of list

                    # Get reference to GT model
                    GT_file = None
                    if request.POST.get("pcGround") == "on":
                        for file in file_set:
                            if "input" in file.name:
                                GT_file = file
                                break

                    # Generate questions and respective choices
                    for i, j in comparisons_list:
                        question = ExperimentQuestion(question_num=question_counter,
                                                      question_text='Question ' + str(question_counter),
                                                      experiment=experimentInstance)
                        question.save()
                        question_counter += 1

                        algorithm_name_i = file_set[i].name.split('_', 1)[1]  # Gets name of file after first '_'
                        algorithm_name_i = algorithm_name_i.split('.')[0]  # Removes file extension

                        algorithm_name_j = file_set[j].name.split('_', 1)[1]  # Gets name of file after first '_'
                        algorithm_name_j = algorithm_name_j.split('.')[0]  # Removes file extension

                        Pairwise.objects.create(question=question, choice_algorithm=algorithm_name_i,
                                                choice_text="Test", choice_image=file_set[i])
                        Pairwise.objects.create(question=question, choice_algorithm=algorithm_name_j,
                                                choice_text="Test", choice_image=file_set[j])

                        if request.POST.get("pcGround") == "on":
                            PairwiseGroundTruth.objects.create(question=question,
                                                               choice_text="Ground Truth", choice_image=GT_file)

                return HttpResponseRedirect(reverse('experimentApp:experimentDetail', args=(experimentSlug,)))

        else:
            if request.FILES.getlist('uploadFileName') is None:
                return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                               'error_message': 'Please upload the '
                                                                                                'images required for '
                                                                                                'the experiment'})
            else:
                return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                               'error_message': 'Please enter a valid '
                                                                                                'title and description'})

    return render(request, 'experimentApp/stageView.html', {'title': 'Error',
                                                            'status_message': 'Error on requesting view: wrong request'
                                                                              ' method. Please attempt to create an'
                                                                              ' experiment again by navigating to home.'})


# View to create ranking experiment on POST request. Gets necessary files and options, then creates models for the
# experiment according to the options
@login_required
def createExperimentRK(request):
    if request.method == 'POST':
        experimentForm = ExperimentForm(request.POST)

        experimentFullForm = ExperimentForm(request.POST or None, request.FILES or None)

        if experimentFullForm.is_valid():
            experimentInstance = experimentForm.save(commit=False)
            experimentInstance.question_type = 'RANKING'
            experimentInstance.save()

            # Generates and saves experiment slug
            experimentSlug = generateUniqueSlug()
            ExperimentSlug.objects.create(experiment=experimentInstance, slug=experimentSlug)

            # Save custom colour options
            if request.POST.get("customColours"):
                ExperimentCustomColours.objects.create(experiment=experimentInstance,
                                                       text_colour=request.POST.get("textColourPicker"),
                                                       background_colour=request.POST.get("backgroundColourPicker"))

            # Save refresher options
            if request.POST.get("radRef"):
                time_shown = request.POST.get("timeVal")
                if request.POST.get("refChoice") == "col":
                    custom_colour = request.POST.get("colourpicker")
                    experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                              time_shown=time_shown, custom_colour=custom_colour,
                                                              custom_image=None)
                    experimentRefresher.save()
                else:
                    custom_image = request.FILES.get("refImage")
                    if custom_image is not None:
                        experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                                  time_shown=time_shown, custom_colour="",
                                                                  custom_image=custom_image)
                        experimentRefresher.save()
                    else:
                        return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                                       'error_message': 'Please upload '
                                                                                                        'a refresher image'})

            # Sorts list of files into list of list(s), where each sublist contains files with same suffix
            if request.POST.get("uploadChoice") == "file":
                files = request.FILES.getlist('uploadFileName')
                sorted_files = sortInputFiles(files, [])
            else:
                sorted_files = sortInputDirs(request)

            # Check each image set has consistent resolution
            for file_set in sorted_files:
                res = None
                for file in file_set:

                    im = Image.open(file)
                    if res is None:
                        res = im.size
                    elif res != im.size:
                        return render(request, 'experimentApp/createExperiment.html',
                                      {'experimentForm': experimentForm,
                                       'error_message': 'Please upload file sets with consistent resolutions'})

            question_counter = 1
            for file_set in sorted_files:

                question = ExperimentQuestion(question_num=question_counter,
                                              question_text='Question ' + str(question_counter),
                                              experiment=experimentInstance)
                question.save()
                question_counter += 1

                choice_counter = 0  # Separate counter used for choices, so when ground-truth enabled it is not included
                for file in file_set:
                    algorithm_name = file.name.split('_', 1)[1]  # Gets name of file after first '_'
                    algorithm_name = algorithm_name.split('.')[0]  # Removes file extension

                    if (request.POST.get("rkGround") == "on") and ("input" in file.name):
                        RankingGroundTruth.objects.create(question=question, choice_text="GT Choice",
                                                          choice_image=file)
                    else:
                        Ranking.objects.create(question=question, choice_algorithm=algorithm_name,
                                               choice_text="Choice " + str(choice_counter), choice_image=file)
                        choice_counter += 1

            return HttpResponseRedirect(reverse('experimentApp:experimentDetail', args=(experimentSlug,)))

        else:
            return render(request, 'experimentApp/stageView.html',
                          {'title': 'Error',
                           'status_message': 'Error on requesting view: wrong request'
                                             ' method. Please attempt to create an'
                                             ' experiment again by navigating to home.'})


# View to create rating experiment on POST request. Gets necessary files and options, then creates models for the
# experiment according to the options
@login_required
def createExperimentRT(request):
    if request.method == 'POST':
        experimentForm = ExperimentForm(request.POST)

        experimentFullForm = ExperimentForm(request.POST or None, request.FILES or None)

        if experimentFullForm.is_valid():
            experimentInstance = experimentForm.save(commit=False)
            experimentInstance.question_type = 'RATING'
            experimentInstance.save()

            # Generates and saves experiment slug
            experimentSlug = generateUniqueSlug()
            ExperimentSlug.objects.create(experiment=experimentInstance, slug=experimentSlug)

            # Save custom colour options
            if request.POST.get("customColours"):
                ExperimentCustomColours.objects.create(experiment=experimentInstance,
                                                       text_colour=request.POST.get("textColourPicker"),
                                                       background_colour=request.POST.get("backgroundColourPicker"))

            # Save refresher options
            if request.POST.get("radRef"):
                time_shown = request.POST.get("timeVal")
                if request.POST.get("refChoice") == "col":
                    custom_colour = request.POST.get("colourpicker")
                    experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                              time_shown=time_shown, custom_colour=custom_colour,
                                                              custom_image=None)
                    experimentRefresher.save()
                else:
                    custom_image = request.FILES.get("refImage")
                    if custom_image is not None:
                        experimentRefresher = ExperimentRefresher(experiment=experimentInstance,
                                                                  time_shown=time_shown, custom_colour="",
                                                                  custom_image=custom_image)
                        experimentRefresher.save()
                    else:
                        return render(request, 'experimentApp/createExperiment.html', {'experimentForm': experimentForm,
                                                                                       'error_message': 'Please upload '
                                                                                                        'a refresher image'})

            # Sorts list of files into list of list(s), where each sublist contains files with same suffix
            if request.POST.get("uploadChoice") == "file":
                files = request.FILES.getlist('uploadFileName')
                sorted_files = sortInputFiles(files, [])
            else:
                sorted_files = sortInputDirs(request)

            # Check each image set has consistent resolution
            for file_set in sorted_files:
                res = None
                for file in file_set:

                    im = Image.open(file)
                    if res is None:
                        res = im.size
                    elif res != im.size:
                        return render(request, 'experimentApp/createExperiment.html',
                                      {'experimentForm': experimentForm,
                                       'error_message': 'Please upload file sets with consistent resolutions'})

            # Get options
            ground_truth = request.POST.get("rtGround") == "on"

            select_choice = request.POST.get("select_choice")
            if select_choice is None:
                return HttpResponse("Error: select option for rating")

            range_lower_bound = request.POST.get("rtLowerBound")
            range_upper_bound = request.POST.get("rtUpperBound")

            question_counter = 1
            for file_set in sorted_files:

                question = ExperimentQuestion(question_num=question_counter,
                                              question_text='Question ' + str(question_counter),
                                              experiment=experimentInstance)
                question.save()
                question_counter += 1

                choice_counter = 0  # Separate counter used for choices, so when ground-truth enabled it is not included
                for file in file_set:
                    algorithm_name = file.name.split('_', 1)[1]  # Gets name of file after first '_'
                    algorithm_name = algorithm_name.split('.')[0]  # Removes file extension

                    if ground_truth and ("input" in file.name):
                        RatingGroundTruth.objects.create(question=question, choice_text="Choice GT",
                                                         choice_image=file)
                    else:
                        Rating.objects.create(question=question, choice_algorithm=algorithm_name,
                                              choice_text="Choice " + str(choice_counter), choice_image=file,
                                              select_choice=select_choice,
                                              range_lower_bound=range_lower_bound, range_upper_bound=range_upper_bound)
                        choice_counter += 1

            return HttpResponseRedirect(reverse('experimentApp:experimentDetail', args=(experimentSlug,)))

        else:
            return render(request, 'experimentApp/stageView.html',
                          {'title': 'Error',
                           'status_message': 'Error on requesting view: wrong request'
                                             ' method. Please attempt to create an'
                                             ' experiment again by navigating to home.'})


# View to force users to sign consent form before they take experiment. Users are tracked on which experiment they are
# taking through their session, thus we "register" user through sessions to this experiment with unique id to
# differentiate between their previous answers and other user's answers
def experimentConsent(request, experiment_slug):

    # Get experiment associated with given slug
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment

    # If user has started experiment
    if request.method == 'POST':

        # Attempt to check if user has registered for this experiment
        try:
            request.session['session_name']
        except KeyError:
            # Register user for experiment, and pass id to session so future questions answers for this experiment
            # can be verified
            experimentRegister = ExperimentRegister(experiment=experiment)
            experimentRegister.save()
            request.session['session_name'] = str(experimentRegister.pk)
        else:
            # Create new session id for user if they choose to do a experiment again
            experimentRegister = ExperimentRegister(experiment=experiment)
            experimentRegister.save()
            request.session['session_name'] = str(experimentRegister.pk)

        return HttpResponseRedirect(reverse('experimentApp:experimentQuestion', args=(experiment_slug, 1)))
    else:
        return render(request, 'experimentApp/experimentConsent.html', {'experiment': experiment})


# Admin view of experiment, admins can view the experiment, view+download results and delete experiment.
@login_required
def experimentDetail(request, experiment_slug):

    # Get experiment associated with given slug
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment

    experiment_url = '/experiment/' + experiment_slug + '/'

    # Check if custom colours used
    try:
        experimentColours = get_object_or_404(ExperimentCustomColours, experiment=experiment)
        experimentColours = True
    except Http404:
        experimentColours = False

    return render(request, 'experimentApp/experimentDetail.html', {'experiment_slug': experiment_slug,
                                                                   'experiment_title': experiment.experiment_title,
                                                                   'experiment_description': experiment.experiment_description,
                                                                   'pub_date': experiment.pub_date,
                                                                   'experiment_url': experiment_url,
                                                                   'question_type': experiment.question_type,
                                                                   'experimentColours': experimentColours})


# View to delete given experiment with pk
@login_required
def deleteExperimentView(request, experiment_slug):
    experiment_id = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment.pk
    Experiment.objects.filter(pk=experiment_id).delete()
    return HttpResponseRedirect(reverse('experimentApp:index'))


# View to preprocess question depending on the question type and display to the user.
def experimentQuestion(request, experiment_slug, question_num):
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment
    question = get_object_or_404(ExperimentQuestion, experiment=experiment, question_num=question_num)

    # Get error message if exists, then delete from user session
    error_message = None
    try:
        error_message = request.session['question_error_message']
        del request.session['question_error_message']
    except KeyError:
        pass

    # Attempt to check if user has registered for this experiment
    try:
        experiment_register_pk = request.session['session_name']
        experiment_register = get_object_or_404(ExperimentRegister, pk=experiment_register_pk)

        if experiment_register.experiment.pk != experiment.pk:
            return render(request, 'experimentApp/stageView.html',
                          {'title': 'Error',
                           'status_message': 'Invalid session: Please sign up for the experiment'})

    except (KeyError, Http404):
        return render(request, 'experimentApp/stageView.html',
                      {'title': 'Error',
                       'status_message': 'Invalid session: Please sign up for the experiment'})
    else:

        # Get custom text+background colours associated with experiment if exists
        try:
            experimentColours = get_object_or_404(ExperimentCustomColours, experiment=experiment)
            text_colour = experimentColours.text_colour
            background_colour = experimentColours.background_colour
        except Http404:
            text_colour = None
            background_colour = None

        # Get refresher image associated with experiment if exists
        try:
            experimentRefresher = get_object_or_404(ExperimentRefresher, experiment=experiment)
            time_shown = experimentRefresher.time_shown
            custom_colour = experimentRefresher.custom_colour
            custom_image = experimentRefresher.custom_image
        except Http404:
            time_shown = None
            custom_colour = None
            custom_image = None

        if experiment.question_type == 'pairwise-comparison':
            choice_set = Pairwise.objects.filter(question=question)

            try:
                groundTruth = get_object_or_404(PairwiseGroundTruth, question=question)
            except Http404:

                # Since we limit 4 choices per row on the website, we organise the data to be manipulated easier
                choice_list = []
                row = []
                for index, choice in enumerate(choice_set):
                    if index % 4 == 0 and index != 0:
                        choice_list.append(row)
                        row = []
                    row.append(choice)

                # Add on remaining row, even if not "full" to 4 choices, if not empty
                if row:
                    choice_list.append(row)

                return render(request, 'experimentApp/experimentQuestion.html',
                              {'question_type': experiment.question_type, 'question': question,
                               'choice_list': choice_list,
                               'experiment_slug': experiment_slug, 'question_error_message': error_message,
                               'time_shown': time_shown,
                               'rf_colour': custom_colour,
                               'rf_image': custom_image,
                               'text_colour': text_colour,
                               'background_colour': background_colour})
            else:

                # Since we limit 4 choices per row on the website, we organise the data to be manipulated easier
                choice_list = []
                row = []
                for index, choice in enumerate(choice_set):
                    if index % 4 == 0 and index != 0:
                        choice_list.append(row)
                        row = []
                    row.append(choice)

                # Add on remaining row, even if not "full" to 4 choices, if not empty
                if row:
                    choice_list.append(row)

                return render(request, 'experimentApp/experimentQuestion.html',
                              {'question_type': experiment.question_type, 'question': question,
                               'choice_list': choice_list,
                               'experiment_slug': experiment_slug, 'groundTruth': groundTruth,
                               'question_error_message': error_message,
                               'time_shown': time_shown,
                               'rf_colour': custom_colour,
                               'rf_image': custom_image,
                               'text_colour': text_colour,
                               'background_colour': background_colour})

        elif experiment.question_type == 'RANKING':
            ranking_set = Ranking.objects.filter(question=question)

            try:
                groundTruth = get_object_or_404(RankingGroundTruth, question=question)
            except Http404:
                return render(request, 'experimentApp/experimentQuestion.html',
                              {'question_type': experiment.question_type, 'question': question,
                               'ranking_set': ranking_set, 'experiment_slug': experiment_slug,
                               'question_error_message': error_message,
                               'time_shown': time_shown,
                               'rf_colour': custom_colour,
                               'rf_image': custom_image,
                               'text_colour': text_colour,
                               'background_colour': background_colour})
            else:
                return render(request, 'experimentApp/experimentQuestion.html',
                              {'question_type': experiment.question_type, 'question': question,
                               'ranking_set': ranking_set, 'experiment_slug': experiment_slug, 'groundTruth': groundTruth,
                               'question_error_message': error_message,
                               'time_shown': time_shown,
                               'rf_colour': custom_colour,
                               'rf_image': custom_image,
                               'text_colour': text_colour,
                               'background_colour': background_colour})

        elif experiment.question_type == 'RATING':
            rating_set = Rating.objects.filter(question=question)
            num_radio_choices = rating_set[0].range_upper_bound - rating_set[
                0].range_lower_bound + 1  # Plus one as exclusive

            try:
                groundTruth = get_object_or_404(RatingGroundTruth, question=question)
            except Http404:

                # Since INPUT_FIELD and SLIDER are organised in rows, we preprocess the data separately
                if rating_set[0].select_choice == "INPUT_FIELD" or rating_set[0].select_choice == "SLIDER":

                    # Since we limit 4 choices per row on the website, we organise the data to be manipulated easier
                    rating_list = []
                    row = []
                    for index, choice in enumerate(rating_set):
                        if index % 4 == 0 and index != 0:
                            rating_list.append(row)
                            row = []
                        row.append(choice)

                    # Add on remaining row, even if not "full" to 4 choices, if not empty
                    if row:
                        rating_list.append(row)

                    return render(request, 'experimentApp/experimentQuestion.html',
                                  {'question_type': experiment.question_type, 'question': question,
                                   'rating_list': rating_list,
                                   'experiment_slug': experiment_slug, 'question_error_message': error_message,
                                   'select_choice': rating_set[0].select_choice,
                                   'range_lower_bound': rating_set[0].range_lower_bound,
                                   'range_upper_bound': rating_set[0].range_upper_bound,
                                   'num_radio_choices': num_radio_choices,
                                   'time_shown': time_shown,
                                   'rf_colour': custom_colour,
                                   'rf_image': custom_image,
                                   'text_colour': text_colour,
                                   'background_colour': background_colour})

                else:
                    return render(request, 'experimentApp/experimentQuestion.html',
                                  {'question_type': experiment.question_type, 'question': question,
                                   'rating_list': rating_set,
                                   'experiment_slug': experiment_slug, 'question_error_message': error_message,
                                   'select_choice': rating_set[0].select_choice,
                                   'range_lower_bound': rating_set[0].range_lower_bound,
                                   'range_upper_bound': rating_set[0].range_upper_bound,
                                   'num_radio_choices': num_radio_choices,
                                   'time_shown': time_shown,
                                   'rf_colour': custom_colour,
                                   'rf_image': custom_image,
                                   'text_colour': text_colour,
                                   'background_colour': background_colour})

            else:

                # Since INPUT_FIELD and SLIDER are organised in rows, we preprocess the data seperately
                if rating_set[0].select_choice == "INPUT_FIELD" or rating_set[0].select_choice == "SLIDER":

                    # Since we limit 4 choices per row on the website, we organise the data to be manipulated easier
                    rating_list = []
                    row = []
                    for index, choice in enumerate(rating_set):
                        if index % 4 == 0 and index != 0:
                            rating_list.append(row)
                            row = []
                        row.append(choice)

                    # Add on remaining row, even if not "full" to 4 choices, if not empty
                    if row:
                        rating_list.append(row)

                    return render(request, 'experimentApp/experimentQuestion.html',
                                  {'question_type': experiment.question_type, 'question': question,
                                   'rating_list': rating_list,
                                   'experiment_slug': experiment_slug, 'groundTruth': groundTruth,
                                   'question_error_message': error_message,
                                   'select_choice': rating_set[0].select_choice,
                                   'range_lower_bound': rating_set[0].range_lower_bound,
                                   'range_upper_bound': rating_set[0].range_upper_bound,
                                   'num_radio_choices': num_radio_choices,
                                   'time_shown': time_shown,
                                   'rf_colour': custom_colour,
                                   'rf_image': custom_image,
                                   'text_colour': text_colour,
                                   'background_colour': background_colour})

                else:
                    return render(request, 'experimentApp/experimentQuestion.html',
                                  {'question_type': experiment.question_type, 'question': question,
                                   'rating_list': rating_set,
                                   'experiment_slug': experiment_slug, 'groundTruth': groundTruth,
                                   'question_error_message': error_message,
                                   'select_choice': rating_set[0].select_choice,
                                   'range_lower_bound': rating_set[0].range_lower_bound,
                                   'range_upper_bound': rating_set[0].range_upper_bound,
                                   'num_radio_choices': num_radio_choices,
                                   'time_shown': time_shown,
                                   'rf_colour': custom_colour,
                                   'rf_image': custom_image,
                                   'text_colour': text_colour,
                                   'background_colour': background_colour})


# View to control storing user's choice for experiment question in database
def vote(request, experiment_slug, question_num):
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment
    question = get_object_or_404(ExperimentQuestion, experiment=experiment, question_num=question_num)

    no_questions = len(ExperimentQuestion.objects.filter(experiment=experiment))

    if experiment.question_type == 'pairwise-comparison':
        choice_set = Pairwise.objects.filter(question=question)

        # Check if option was chosen, as this isn't guaranteed for radio
        try:
            selected_choice = get_object_or_404(Pairwise, pk=request.POST['choice'])
        except (KeyError, Pairwise.DoesNotExist):
            request.session['question_error_message'] = "You didn't select a choice."
            return HttpResponseRedirect(
                reverse('experimentApp:experimentQuestion', args=(experiment_slug, question.question_num)))
            # return render(request, 'experimentApp/experimentQuestion.html',
            #               {'question_type': experiment.question_type, 'question': question, 'choice_set': choice_set,
            #               'experiment_id': experiment_id, 'error_message': "You didn't select a choice."})

        else:
            # Attempt to check if user has registered for this experiment
            try:
                experiment_register_pk = request.session['session_name']
                experimentRegister = ExperimentRegister(pk=experiment_register_pk)
            except KeyError:
                return HttpResponse("Invalid session: Please sign up for the experiment")
                # REDIRECT TO START OF experiment
            else:

                # Check if user has already answered this question
                try:
                    previous_answer = get_object_or_404(PairwiseChoice, pairwise__in=choice_set,
                                                        experimentRegister=experimentRegister)
                except Http404:  # No previous answer found
                    pass
                else:
                    previous_answer.delete()

                # Save answer
                for pairwise in choice_set:
                    if selected_choice.pk == pairwise.pk:
                        pairwiseChoice = PairwiseChoice(pairwise=pairwise, experimentRegister=experimentRegister,
                                                        choice=1)
                        pairwiseChoice.save()

    elif experiment.question_type == 'RANKING':

        # Attempt to check if user has registered for this experiment
        try:
            experiment_register_pk = request.session['session_name']
            experimentRegister = ExperimentRegister(pk=experiment_register_pk)
        except KeyError:
            return HttpResponse("Invalid session: Please sign up for the experiment")
            # REDIRECT TO START OF EXPERIMENT
        else:

            # Check if user has already answered this question
            ranking_set = Ranking.objects.filter(question=question)
            previous_answers = RankingChoice.objects.filter(ranking__in=ranking_set,
                                                            experimentRegister=experimentRegister)
            if previous_answers:
                for answer in previous_answers:
                    answer.delete()

            # We have an ordered list of ranking primary keys returned if valid
            form = OrderingForm(request.POST)
            if form.is_valid():
                ordered_ids = form.cleaned_data["ordering"].split(',')

                # We create a new model for every ranking, containing its position in the ordering
                for counter, ranking_pk in enumerate(ordered_ids):
                    ranking = get_object_or_404(Ranking, pk=ranking_pk)
                    RankingChoice.objects.create(ranking=ranking, experimentRegister=experimentRegister,
                                                 position=counter + 1)  # Plus one because we start counting from 1

    elif experiment.question_type == 'RATING':
        rating_choices = Rating.objects.filter(question=question)

        # Attempt to check if user has registered for this experiment
        try:
            experiment_register_pk = request.session['session_name']
            experimentRegister = ExperimentRegister(pk=experiment_register_pk)
        except KeyError:
            return HttpResponse("Invalid session: Please sign up for the experiment")
            # REDIRECT TO START OF EXPERIMENT
        else:

            # Check if user has already answered this question
            rating_set = Rating.objects.filter(question=question)
            previous_answers = RatingChoice.objects.filter(rating__in=rating_set, experimentRegister=experimentRegister)
            if previous_answers:
                for answer in previous_answers:
                    answer.delete()

            if rating_set[0].select_choice == 'INPUT_FIELD':
                # Check all user answers are within legal range
                for x, rating in enumerate(rating_choices):
                    value = request.POST.get('ratingChoice' + str(x))
                    try:
                        if int(value) < 0 or int(value) > 100:
                            request.session['question_error_message'] = "Choose a value between 0 and 100"
                            return HttpResponseRedirect(
                                reverse('experimentApp:experimentQuestion',
                                        args=(experiment_slug, question.question_num)))
                    except ValueError:  # If number is not inputted
                        request.session['question_error_message'] = "Choose a value between 0 and 100"
                        return HttpResponseRedirect(
                            reverse('experimentApp:experimentQuestion', args=(experiment_slug, question.question_num)))

                # For each choice, get its given corresponding rating
                for x, rating in enumerate(rating_choices):
                    RatingChoice.objects.create(rating=rating, experimentRegister=experimentRegister,
                                                rating_value=request.POST.get('ratingChoice' + str(x)))

            elif rating_set[0].select_choice == 'RADIO':
                # For each rating, find which radio has been activated, if none raise error
                for x, rating in enumerate(rating_choices):
                    for y in range(rating_set[0].range_lower_bound, rating_set[0].range_upper_bound + 1):
                        if request.POST.get(str(x) + 'ratingChoiceRadio' + str(y)) == 'on':
                            RatingChoice.objects.create(rating=rating, experimentRegister=experimentRegister,
                                                        rating_value=y)

            elif rating_set[0].select_choice == 'SLIDER':
                for x, rating in enumerate(rating_choices):
                    value = request.POST.get('ratingChoiceSlider' + str(x))
                    RatingChoice.objects.create(rating=rating, experimentRegister=experimentRegister,
                                                rating_value=value)

    else:
        raise Http404

    # If any of the votes succeeded, send user to next question if not at end of experiment
    if question_num == no_questions:
        return render(request, 'experimentApp/experimentFinish.html')
    else:
        return HttpResponseRedirect(
            reverse('experimentApp:experimentQuestion', args=(experiment_slug, question.question_num + 1)))


# View to inform user they have finished experiment
def experimentFinish(request, experiment_slug):
    return render(request, 'experimentApp/experimentFinish.html')


# View to show admin results of given experiment
@login_required
def results(request, experiment_slug):

    # Get experiment associated with given slug
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment

    experiment = get_object_or_404(Experiment, pk=experiment.pk)
    question_list = ExperimentQuestion.objects.filter(experiment=experiment)

    if experiment.question_type == 'pairwise-comparison':
        # Given experiment, calculate total votes per algorithm, and how each user voted per question

        # List of all choices associated with each question in this experiment
        choice_list = Pairwise.objects.filter(question__in=question_list)

        # List of all user answers associated with above choices
        answer_list = PairwiseChoice.objects.filter(pairwise__in=choice_list)

        # Create dict of all algorithms applied
        total_votes_dict = {}
        for choice in choice_list:
            algorithm_name = choice.choice_algorithm

            if algorithm_name not in total_votes_dict:
                total_votes_dict[algorithm_name] = 0

        # Create list of all users who answered this experiment
        user_list = []
        for answer in answer_list:
            alg = answer.pairwise.choice_algorithm
            total_votes_dict[alg] += answer.choice

            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Create dict, holding answers for each question for each user
        # e.g. {'User1': {'Question1': {'alg1': '1', 'alg2': '0'} }
        user_dict = {}
        question_name_list = []
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            question_dict = {}
            for question in question_list:

                # Check if user has answered question, if not output ""
                pairwise_list = Pairwise.objects.filter(question=question)
                try:
                    choice = get_object_or_404(PairwiseChoice, pairwise__in=pairwise_list,
                                               experimentRegister=experimentRegister)

                    for pairwise in pairwise_list:
                        if choice.pairwise == pairwise:
                            question_dict[str(question.question_num) + '_' + pairwise.choice_algorithm] = 1
                        else:
                            question_dict[str(question.question_num) + '_' + pairwise.choice_algorithm] = 0

                except Http404:
                    for pairwise in pairwise_list:
                        question_dict[str(question.question_num) + '_' + pairwise.choice_algorithm] = ""

                for pairwise in Pairwise.objects.filter(question=question):

                    # Create list of all question names, used for exporting the data
                    if (str(question.question_num) + '_' + pairwise.choice_algorithm) not in question_name_list:
                        question_name_list.append(str(question.question_num) + '_' + pairwise.choice_algorithm)

            user_dict[user_pk] = question_dict

        return render(request, 'experimentApp/results.html',
                      {'experiment_slug': experiment_slug, 'question_list': question_list, 'choice_list': choice_list,
                       'total_votes_dict': total_votes_dict,
                       'experiment_title': experiment.experiment_title, 'type': experiment.question_type,
                       'user_dict': user_dict, 'question_name_list': question_name_list})

    elif experiment.question_type == 'RANKING':
        # Given experiment, for each algorithm count number of times it is in each position
        # ASSUMING CONSTANT NO. ALGORITHMS

        # List all choices associated with each question in this experiment
        ranking_list = Ranking.objects.filter(question__in=question_list)

        # List all decided rankings associated with above
        answer_list = RankingChoice.objects.filter(ranking__in=ranking_list)

        # Create list of all users who answered this experiment
        user_list = []
        for answer in answer_list:
            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Create dict showing votes per algorithm per question
        # e.g. {'User1': {'Question1_alg1': 2, 'Question1_alg2': 1, 'Question1_alg3': 3 } }
        user_dict = {}
        question_name_list = []
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            question_dict = {}
            for question in question_list:

                for ranking in Ranking.objects.filter(question=question):

                    # Attempt to get the answer, if none exists then replace value with ""
                    try:
                        answer = get_object_or_404(RankingChoice, ranking=ranking,
                                                   experimentRegister=experimentRegister)
                        question_dict[str(question.question_num) + '_' + ranking.choice_algorithm] = answer.position
                    except:
                        question_dict[str(question.question_num) + '_' + ranking.choice_algorithm] = ""

                    # Create list of all question names, used for exporting the data
                    if (str(question.question_num) + '_' + ranking.choice_algorithm) not in question_name_list:
                        question_name_list.append(str(question.question_num) + '_' + ranking.choice_algorithm)

            user_dict[user_pk] = question_dict

        return render(request, 'experimentApp/results.html',
                      {'experiment_slug': experiment_slug, 'question_list': question_list,
                       'experiment_title': experiment.experiment_title, 'question_name_list': question_name_list,
                       'type': experiment.question_type,
                       'user_dict': user_dict})

    elif experiment.question_type == 'RATING':
        # e.g. {'Question1': {'alg1': 55, 'alg2': 42} }

        # List of all choices associated with each question in this experiment
        rating_list = Rating.objects.filter(question__in=question_list)

        # List of all user answers associated with above choices
        answer_list = RatingChoice.objects.filter(rating__in=rating_list)

        # Create dict of all algorithms applied
        total_votes_dict = {}
        for choice in rating_list:
            algorithm_name = choice.choice_algorithm

            if algorithm_name not in total_votes_dict:
                total_votes_dict[algorithm_name] = 0

        # Create list of all users who answered this experiment
        user_list = []
        for answer in answer_list:
            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Create dict, holding answers for each question for each user
        # e.g. {'User1': {'Question1': {'alg1': '1', 'alg2': '0'} }
        user_dict = {}
        question_name_list = []
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            question_dict = {}
            for question in question_list:

                for rating in Rating.objects.filter(question=question):

                    # Attempt to get user choice for this question, if none exists then the user didn't choose
                    # the queried option
                    try:
                        answer = get_object_or_404(RatingChoice, rating=rating, experimentRegister=experimentRegister)
                        question_dict[str(question.question_num) + '_' + rating.choice_algorithm] = answer.rating_value
                    except Http404:
                        question_dict[str(question.question_num) + '_' + rating.choice_algorithm] = ""

                    # Create list of all question names, used for exporting the data
                    if (str(question.question_num) + '_' + rating.choice_algorithm) not in question_name_list:
                        question_name_list.append(str(question.question_num) + '_' + rating.choice_algorithm)

            user_dict[user_pk] = question_dict

        return render(request, 'experimentApp/results.html',
                      {'experiment_slug': experiment_slug, 'question_list': question_list,
                       'experiment_title': experiment.experiment_title, 'user_dict': user_dict,
                       'type': experiment.question_type,
                       'question_name_list': question_name_list})


# Admin view to manipulate experiment results to be saved as .csv
@login_required
def resultsDownload(request, experiment_slug):

    # Get experiment associated with given slug
    experiment = get_object_or_404(ExperimentSlug, slug=experiment_slug).experiment

    # Check if custom colours
    try:
        experimentColours = get_object_or_404(ExperimentCustomColours, experiment=experiment)
    except Http404:
        experimentColours = None

    question_list = ExperimentQuestion.objects.filter(experiment=experiment)

    # Modify response so client will download given file
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="' + str(experiment.experiment_title) + '_results.csv"'

    writer = csv.writer(response, delimiter=',')

    if experiment.question_type == 'pairwise-comparison':
        # List of all choices associated with each question in this experiment
        choice_list = Pairwise.objects.filter(question__in=question_list)

        # List of all user answers associated with above choices
        answer_list = PairwiseChoice.objects.filter(pairwise__in=choice_list)

        # Create list of all users who answered this experiment
        # REFACTOR
        user_list = []
        for answer in answer_list:
            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Write headers
        header_list = []
        for question in question_list:
            question_pairwise = Pairwise.objects.filter(question=question)

            for pairwise in question_pairwise:
                header_list.append(str(question.question_num) + pairwise.choice_algorithm)

        # Add headers custom colours if necessary
        if experimentColours is not None:
            header_list.append('text_colour')
            header_list.append('background_colour')

        writer.writerow(header_list)

        # Write result for each user
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            user_answers_list = []
            for question in question_list:

                # Check if user has answered question, if not output ""
                pairwise_list = Pairwise.objects.filter(question=question)
                try:
                    choice = get_object_or_404(PairwiseChoice, pairwise__in=pairwise_list,
                                               experimentRegister=experimentRegister)

                    for pairwise in pairwise_list:
                        if choice.pairwise == pairwise:
                            user_answers_list.append(1)
                        else:
                            user_answers_list.append(0)

                except Http404:
                    for _ in pairwise_list:
                        user_answers_list.append("")

            # Custom colours
            if experimentColours is not None:
                user_answers_list.append(experimentColours.text_colour)
                user_answers_list.append(experimentColours.background_colour)

            writer.writerow(user_answers_list)

        return response

    elif experiment.question_type == 'RANKING':
        # List of all choices associated with each question in this experiment
        ranking_list = Ranking.objects.filter(question__in=question_list)

        # List of all user answers associated with above choices
        answer_list = RankingChoice.objects.filter(ranking__in=ranking_list)

        # Create list of all users who answered this experiment
        # REFACTOR
        user_list = []
        for answer in answer_list:
            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Write headers
        header_list = []
        for question in question_list:
            question_ranking = Ranking.objects.filter(question=question)

            for ranking in question_ranking:
                header_list.append(str(question.question_num) + '_' + ranking.choice_algorithm)

        # Add headers custom colours if necessary
        if experimentColours is not None:
            header_list.append('text_colour')
            header_list.append('background_colour')

        writer.writerow(header_list)

        # Write result for each user
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            user_answers_list = []
            for question in question_list:

                for ranking in Ranking.objects.filter(question=question):

                    # Attempt to get the answer, if none exists then replace value with ""
                    try:
                        answer = get_object_or_404(RankingChoice, ranking=ranking,
                                                   experimentRegister=experimentRegister)
                        user_answers_list.append(answer.position)
                    except Http404:
                        user_answers_list.append("")

            # Custom colours
            if experimentColours is not None:
                user_answers_list.append(experimentColours.text_colour)
                user_answers_list.append(experimentColours.background_colour)

            writer.writerow(user_answers_list)

        return response

    elif experiment.question_type == 'RATING':
        # List of all choices associated with each question in this experiment
        rating_list = Rating.objects.filter(question__in=question_list)

        # List of all user answers associated with above choices
        answer_list = RatingChoice.objects.filter(rating__in=rating_list)

        # Create list of all users who answered this experiment
        # REFACTOR
        user_list = []
        for answer in answer_list:
            if answer.experimentRegister.pk not in user_list:
                user_list.append(answer.experimentRegister.pk)

        # Write headers
        header_list = []
        for question in question_list:
            question_rating = Rating.objects.filter(question=question)

            for rating in question_rating:
                header_list.append(str(question.question_num) + '_' + rating.choice_algorithm)

        # Add headers for min and max possible value
        header_list.append('minimum_value')
        header_list.append('maximum_value')

        # Add headers custom colours if necessary
        if experimentColours is not None:
            header_list.append('text_colour')
            header_list.append('background_colour')

        writer.writerow(header_list)

        # Create dict, holding answers for each question for each user
        for user_pk in user_list:
            experimentRegister = get_object_or_404(ExperimentRegister, pk=user_pk)

            user_answers_list = []
            for question in question_list:

                for rating in Rating.objects.filter(question=question):

                    # Attempt to get user choice for this question, if none exists then the user didn't choose
                    # the queried option
                    try:
                        answer = get_object_or_404(RatingChoice, rating=rating, experimentRegister=experimentRegister)
                        user_answers_list.append(answer.rating_value)
                    except Http404:
                        user_answers_list.append("")

            # Min max
            user_answers_list.append(rating.range_lower_bound)
            user_answers_list.append(rating.range_upper_bound)

            # Custom colours
            if experimentColours is not None:
                user_answers_list.append(experimentColours.text_colour)
                user_answers_list.append(experimentColours.background_colour)

            writer.writerow(user_answers_list)

        return response
