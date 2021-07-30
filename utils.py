import random
import string

from experimentApp.models import ExperimentSlug, ExperimentCustomColours, ExperimentRefresher


# Helper function to save generic details about experiment and options that are present in all types of experiments
def saveExperimentInstance(request, experimentForm, experiment_type, question_type):

    # Save Experiment model
    experimentInstance = experimentForm.save(commit=False)
    experimentInstance.experiment_type = experiment_type
    experimentInstance.question_type = question_type
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
            ExperimentRefresher.objects.create(experiment=experimentInstance,
                                               time_shown=time_shown, custom_colour=custom_colour,
                                               custom_image=None)
        else:
            custom_image = request.FILES.get("refImage")
            ExperimentRefresher.objects.create(experiment=experimentInstance,
                                time_shown=time_shown, custom_colour="",
                                custom_image=custom_image)

    return experimentInstance, experimentSlug


# Given list of files, generates new list of tuples where each tuple contains all files with same
# prefix before a '_'
def sortInputFiles(oldFileList, newFileList):
    if len(oldFileList) == 0:
        return newFileList

    file = oldFileList[0]
    file_list = [file]
    oldFileList.remove(file)
    file_prefix = file.name.split('_')[0]

    for f in list(reversed(oldFileList)):
        f_prefix = f.name.split('_')[0]
        if file_prefix == f_prefix:
            oldFileList.remove(f)
            file_list.append(f)

    newFileList.append(file_list)
    n = sortInputFiles(oldFileList, newFileList)
    return n


def sortInputDirs(request):

    fileList = []
    dir_counter = 0
    while True:
        # If we have reached the end of file uploads
        if not ('uploadDir' + str(dir_counter)) in request.FILES:
            break
        else:
            files = request.FILES.getlist('uploadDir' + str(dir_counter))
            fileList.append(files)
            dir_counter += 1

    return fileList


# Generates random 5 letter string of lower+uppercase letters, checks that it is unique with all other
# experiment slugs
def generateUniqueSlug():

    while True:
        slug = ''.join(random.choices(string.ascii_letters, k=5))
        if not ExperimentSlug.objects.filter(slug=slug).exists():
            break

    return slug
