# Generated by Django 4.1.4 on 2024-01-23 22:24

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("walletapp", "0074_collections_images_zip_file"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="collections",
            name="images_zip_files",
        ),
    ]