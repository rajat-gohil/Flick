from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_movie_intelligence_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='TmdbChangesCheckpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feed_name', models.CharField(default='movie_changes', max_length=64, unique=True)),
                ('last_polled_at', models.DateTimeField(blank=True, null=True)),
                ('window_start_date', models.DateField(blank=True, null=True)),
                ('window_end_date', models.DateField(blank=True, null=True)),
                ('current_page', models.PositiveIntegerField(default=1)),
                ('total_pages', models.PositiveIntegerField(default=1)),
                ('changes_detected_count', models.PositiveIntegerField(default=0)),
                ('changes_enqueued_count', models.PositiveIntegerField(default=0)),
                ('is_in_progress', models.BooleanField(default=False)),
                ('lock_token', models.UUIDField(blank=True, null=True)),
                ('lock_generation', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'TMDB Changes Checkpoint',
                'verbose_name_plural': 'TMDB Changes Checkpoints',
            },
        ),
        migrations.CreateModel(
            name='StalenessSweepCheckpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sweep_name', models.CharField(default='90_day_movie_staleness', max_length=64, unique=True)),
                ('last_sweep_completed_at', models.DateTimeField(blank=True, null=True)),
                ('last_scanned_id', models.PositiveIntegerField(default=0)),
                ('is_in_progress', models.BooleanField(default=False)),
                ('records_scanned', models.PositiveIntegerField(default=0)),
                ('records_enqueued', models.PositiveIntegerField(default=0)),
                ('records_skipped', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Staleness Sweep Checkpoint',
                'verbose_name_plural': 'Staleness Sweep Checkpoints',
            },
        ),
    ]
