# Generated by Django 2.0.3 on 2018-08-15 00:05

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import votings.utils


class Migration(migrations.Migration):

    dependencies = [
        ('votings', '0003_auto_20180810_1704'),
    ]

    operations = [
        migrations.AddField(
            model_name='medianvoting',
            name='voting_num',
            field=models.PositiveIntegerField(default=0, help_text='Abstimmungsnummer innerhalb der Gruppe'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='schulzevoting',
            name='voting_num',
            field=models.PositiveIntegerField(default=0, help_text='Abstimmungsnummer innerhalb der Gruppe'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='votinggroup',
            name='group_num',
            field=models.PositiveIntegerField(default=0, help_text='Gruppen Nummer'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='period',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='Erstellungszeitpunkt'),
        ),
        migrations.AlterField(
            model_name='period',
            name='end',
            field=models.DateField(blank=True, default=votings.utils.get_semester_end, help_text='Ende der Periode', null=True),
        ),
        migrations.AlterField(
            model_name='period',
            name='name',
            field=models.CharField(default=votings.utils.get_semester_name, help_text='Name der Abstimmungsperiode, z.B. "Sommersemester 2018"', max_length=150, unique=True),
        ),
        migrations.AlterField(
            model_name='period',
            name='start',
            field=models.DateField(blank=True, default=votings.utils.get_semester_start, help_text='Start der Periode', null=True),
        ),
        migrations.AlterField(
            model_name='votersrevision',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='Erstellungszeitpunkt'),
        ),
        migrations.AlterField(
            model_name='votersrevision',
            name='note',
            field=models.TextField(blank=True, help_text='Optinale Notiz'),
        ),
        migrations.AlterField(
            model_name='votersrevision',
            name='period',
            field=models.ForeignKey(help_text='Periode für diese Revision', on_delete=django.db.models.deletion.CASCADE, to='votings.Period'),
        ),
    ]
