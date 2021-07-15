import random
import string

from experimentApp.models import ExperimentSlug


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
