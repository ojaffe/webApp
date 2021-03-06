# Generated by Django 3.2.4 on 2021-07-09 10:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('experimentApp', '0003_alter_experiment_experiment_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExperimentRefresher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time_shown', models.IntegerField()),
                ('custom_colour', models.CharField(max_length=7)),
                ('custom_image', models.ImageField(upload_to='refresherImages/')),
                ('experiment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='experimentApp.experiment')),
            ],
        ),
    ]
