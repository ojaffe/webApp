from django.urls import path
from . import views

app_name = 'experimentApp'
urlpatterns = [
    path('', views.index, name='index'),
    path('stage/', views.stageView, name='stageView'),
    path('help/', views.helpView, name='helpView'),
    path('about/', views.aboutView, name='aboutView'),
    path('contact/', views.contactView, name='contactView'),

    path('previousExperiments/', views.previousExperimentView, name='previousExperimentView'),
    path('createExperiment/', views.createExperiment, name='createExperiment'),

    path('<str:experiment_slug>/', views.experimentConsent, name='experimentConsent'),
    path('<str:experiment_slug>/detail', views.experimentDetail, name='experimentDetail'),
    path('<str:experiment_slug>/delete', views.deleteExperimentView, name='deleteExperimentView'),
    path('<str:experiment_slug>/<int:question_num>/', views.experimentQuestion, name='experimentQuestion'),
    path('<str:experiment_slug>/<int:question_num>/vote/', views.vote, name='vote'),
    path('<str:experiment_slug>/finish/', views.experimentFinish, name='experimentFinish'),
    path('<str:experiment_slug>>/results/download/', views.resultsDownload, name='resultsDownload'),
]
