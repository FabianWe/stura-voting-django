# Generated by Django 2.2 on 2019-04-12 14:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('votings', '0011_auto_20190412_1401'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='votingcollection',
            options={'permissions': (('view_collection_results', 'Can view results of a collection'), ('enter_collection_results', 'Can enter results for all who are entitled to vote'))},
        ),
    ]
