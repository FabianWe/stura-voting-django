# Generated by Django 2.0.3 on 2018-07-08 11:18

from decimal import Decimal
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('votings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedianVote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.PositiveIntegerField(verbose_name='Value the voter voted for')),
                ('voter', models.ForeignKey(help_text='The voter of this vote', on_delete=django.db.models.deletion.CASCADE, to='votings.Voter')),
            ],
        ),
        migrations.CreateModel(
            name='SchulzeOption',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('option', models.CharField(help_text='Option text', max_length=150)),
            ],
        ),
        migrations.CreateModel(
            name='SchulzeVote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sorting_position', models.IntegerField(help_text='Position in the voting (the smaller the higher the option was voted)')),
                ('option', models.ForeignKey(help_text='The option this entry is created for', on_delete=django.db.models.deletion.CASCADE, to='votings.SchulzeOption')),
                ('voter', models.ForeignKey(help_text='The voter of this vote', on_delete=django.db.models.deletion.CASCADE, to='votings.Voter')),
            ],
        ),
        migrations.CreateModel(
            name='SchulzeVoting',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name of the voting', max_length=150)),
                ('percent_required', models.DecimalField(decimal_places=1, default=Decimal('50.0'), help_text='Percent of votes required, for example 50 (half of all votes) or 75 (three-quarters)', max_digits=4, validators=[django.core.validators.MinValueValidator(Decimal('0.0')), django.core.validators.MaxValueValidator(Decimal('100.0'))])),
                ('group', models.ForeignKey(help_text='Group this voting belongs to', on_delete=django.db.models.deletion.CASCADE, to='votings.VotingGroup')),
            ],
        ),
        migrations.AlterField(
            model_name='medianvoting',
            name='name',
            field=models.CharField(help_text='Name of the voting', max_length=150),
        ),
        migrations.AddField(
            model_name='schulzeoption',
            name='voting',
            field=models.ForeignKey(help_text='Voting this option belongs to', on_delete=django.db.models.deletion.CASCADE, to='votings.SchulzeVoting'),
        ),
        migrations.AddField(
            model_name='medianvote',
            name='voting',
            field=models.ForeignKey(help_text='The voting in question', on_delete=django.db.models.deletion.CASCADE, to='votings.MedianVoting'),
        ),
        migrations.AlterUniqueTogether(
            name='schulzevoting',
            unique_together={('name', 'group')},
        ),
        migrations.AlterUniqueTogether(
            name='schulzevote',
            unique_together={('voter', 'option')},
        ),
        migrations.AlterUniqueTogether(
            name='schulzeoption',
            unique_together={('option', 'voting')},
        ),
        migrations.AlterUniqueTogether(
            name='medianvote',
            unique_together={('voter', 'voting')},
        ),
    ]
