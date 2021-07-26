from django.db import models
from django.utils.timezone import now


# Each experiment has one instance of this model, all models associated with this model directly or indirectly have
# foreign keys to this
class Experiment(models.Model):
    experiment_title = models.CharField(max_length=200)
    experiment_description = models.CharField(max_length=500)
    pub_date = models.DateTimeField('date created', default=now)

    experiment_type = models.CharField(max_length=50)  # 'image' 'video'
    question_type = models.CharField(max_length=50)  # 'pairwise-comparison' 'ranking' 'rating'

    def __str__(self):
        return self.experiment_title


# Model to track which experiments users are doing using sessions
class ExperimentRegister(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)


# Every experiment has a unique slug, used in the experiments URL e.g. https://experiment/JxTFw
class ExperimentSlug(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)

    slug = models.SlugField()


# Options about custom text+background colours, optional for experiment to have this
class ExperimentCustomColours(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)

    text_colour = models.CharField(max_length=7)  # Hex colour
    background_colour = models.CharField(max_length=7)  # Hex colour


# Model to hold information about experiments "refresher" image, which may be shown between questions
class ExperimentRefresher(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)

    time_shown = models.IntegerField()  # In ms
    custom_colour = models.CharField(max_length=7)  # Hex colour
    custom_image = models.ImageField(upload_to='refresherImages/')


# Each question is represented by this model, choices in such question have foreign keys to this
class ExperimentQuestion(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)

    question_num = models.IntegerField()  # Index of question in experimentApp
    question_text = models.CharField(max_length=200)

    def __str__(self):
        return self.question_text


class Pairwise(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_algorithm = models.CharField(max_length=200)  # Name of algorithm applied to image
    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')

    def __str__(self):
        return self.choice_text


class PairwiseGroundTruth(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')


class PairwiseChoice(models.Model):
    pairwise = models.ForeignKey(Pairwise, on_delete=models.CASCADE)
    experimentRegister = models.ForeignKey(ExperimentRegister, on_delete=models.CASCADE)

    choice = models.IntegerField()  # 0 if not chosen, 1 if chosen


# Options about experiment if ranking is used, will be created for all ranking experiments
class RankingOptions(models.Model):
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE)

    randomiseInitialOrdering = models.BooleanField()


class Ranking(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_algorithm = models.CharField(max_length=200)  # Name of algorithm applied to image
    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')

    def __str__(self):
        return self.choice_text


class RankingGroundTruth(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')


class RankingChoice(models.Model):
    ranking = models.ForeignKey(Ranking, on_delete=models.CASCADE)
    experimentRegister = models.ForeignKey(ExperimentRegister, on_delete=models.CASCADE)

    position = models.IntegerField()


RATING_SELECT_CHOICES = (
    ('INPUT_FIELD', 'Input field'),
    ('RADIO', 'Radio'),
    ('SLIDER', 'Slider'),
)


class Rating(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_algorithm = models.CharField(max_length=200)  # Name of algorithm applied to image
    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')

    select_choice = models.CharField(max_length=50, choices=RATING_SELECT_CHOICES)

    range_lower_bound = models.IntegerField(default=0)
    range_upper_bound = models.IntegerField(default=100)

    def __str__(self):
        return self.choice_text


class RatingGroundTruth(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_text = models.CharField(max_length=200)
    choice_image = models.ImageField(upload_to='choiceImages/', default='default/default.jpg')


class RatingChoice(models.Model):
    rating = models.ForeignKey(Rating, on_delete=models.CASCADE)
    experimentRegister = models.ForeignKey(ExperimentRegister, on_delete=models.CASCADE)

    rating_value = models.IntegerField()


# Model to support form
class EmailModel(models.Model):
    subject = models.CharField(max_length=200)
    message = models.CharField(max_length=1000)


class VideoPairwise(models.Model):
    question = models.ForeignKey(ExperimentQuestion, on_delete=models.CASCADE)

    choice_algorithm = models.CharField(max_length=200)  # Name of algorithm applied to image
    choice_text = models.CharField(max_length=200)
    choice_video = models.FileField(upload_to='videos/')
